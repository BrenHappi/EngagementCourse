from flask import Blueprint, current_app, request, jsonify
from flask_login import current_user, login_required
from datetime import datetime, timedelta
from engagement_course.models import EngagementStatus
from pydantic import BaseModel, Field
from engagement_course.utils import get_db
from engagement_course.mail import send_email

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")


class CreateEngagementPayload(BaseModel):
    user_id: int = Field(gt=0)
    race_id: int = Field(gt=0)
    status: EngagementStatus

class UpdateEngagementPayload(BaseModel):
    status: EngagementStatus


def _to_engagement_status(value) -> EngagementStatus | None:
    if isinstance(value, EngagementStatus):
        return value
    if isinstance(value, str):
        try:
            return EngagementStatus(value)
        except ValueError:
            return None
    return None


def _race_accepts_user_category(race, user_category) -> bool:
    if not user_category or not race.categories:
        return False

    for race_category in race.categories:
        if (
            race_category.level == user_category.level
            and race_category.number == user_category.number
        ):
            return True
    return False

@api_bp.route("/engagement", methods=["POST"])
@login_required
def create_engagement():
    db = get_db()

    raw_json = request.get_json(silent=True) or {}
    try:
        payload = CreateEngagementPayload(**raw_json)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Invalid payload: {e}"}), 400

    target_user = db.get_user_by_id(id=payload.user_id)
    if target_user is None:
        return jsonify({"status": "error", "message": "User not found"}), 404

    if target_user.user_id != current_user.user_id:
        return jsonify({"status": "error", "message": "Forbidden"}), 403

    race_id = payload.race_id
    race = db.get_race_by_id(race_id)
    if race is None:
        return jsonify({"status": "error", "message": "Race not found"}), 404
    
    # Check if the user category is compatible with the race
    if not _race_accepts_user_category(race, target_user.category):
        return jsonify({"status": "error", "message": "User category not compatible with race"}), 400
    
    # Checking that the race is in less than 5 days
    now = datetime.now()
    if now + timedelta(days=5) > race.date:
        return jsonify({"status": "error", "message": "Engagements are closed for this race"}), 400

    status = _to_engagement_status(payload.status)
    if status is None:
        return jsonify({"status": "error", "message": "Invalid status"}), 400
    if status == EngagementStatus.VALIDATED:
        return jsonify({"status": "error", "message": "Forbidden"}), 403

    try:
        db.create_engagement(user_id=current_user.id, race=race, status=status)
        manager_email = db.get_manager_for_category(current_user.category).email
        if current_app.config['notify'] and manager_email:
            send_email(
                to_address=manager_email,
                subject=f"Demande inscription de {current_user.firstname} {current_user.lastname} à {race.location} ({race.department}) le {race.date}",
                message=f"Vous avez reçu une nouvelle demande d'inscription de {current_user.firstname} {current_user.lastname} à {race.location} ({race.department}) le {race.date}. "
                        f"Veuillez vous connecter sur {current_app.config['external_url']}/admin pour valider ou refuser cette demande."
            )
        return jsonify({"status": "success", "message": "Engagement created successfully"}), 201
    except ValueError:
        return jsonify({"status": "error", "message": "Failed to create engagement"}), 400  # Duplicate engagement?


@api_bp.route("/engagement/<int:engagement_id>", methods=["GET"])
@login_required
def get_engagement(engagement_id):
    db = get_db()
    engagement = db.get_engagement_by_id(engagement_id)
    if engagement is None:
        return jsonify({
            "status": "error",
            "message": "Engagement not found"
            }), 404
    if engagement.user != current_user:
        return jsonify({"status": "error", "message": "Forbidden"}), 403
    
    return jsonify({
        "status": "success",
        "engagement": {
            "id": engagement.id,
            "user_id": engagement.user.user_id,
            "race_id": engagement.race.race_id,
            "status": engagement.status.name
        }
    }), 200


@api_bp.route("/engagement/user/<int:user_id>", methods=["GET"])
@login_required
def get_user_engagements(user_id):
    db = get_db()
    engagements = db.list_engagements(user_id)
    if not engagements:
        return jsonify({
            "status": "error",
            "message": "No engagements found for this user"
            }), 404
    if user_id != current_user.user_id:
        return jsonify({"status": "error", "message": "Forbidden"}), 403

    return jsonify({
        "status": "success",
        "engagements": [
            {
                "id": engagement.id,
                "user_id": engagement.user.user_id,
                "race_id": engagement.race.race_id,
                "status": engagement.status.name
            }
            for engagement in engagements
        ]
    }), 200


@api_bp.route("/engagement/<int:engagement_id>", methods=["PATCH"])
@login_required
def update_engagement(engagement_id):
    db = get_db()

    engagement = db.get_engagement_by_id(engagement_id)
    if engagement is None:
        return jsonify({"status": "error", "message": "Engagement not found"}), 404
    if engagement.user != current_user:
        return jsonify({"status": "error", "message": "Forbidden"}), 403
    
    current_status = _to_engagement_status(engagement.status)
    if current_status is None:
        return jsonify({"status": "error", "message": "Invalid engagement status"}), 400

    raw_json = request.get_json(silent=True) or {}
    try:
        payload = UpdateEngagementPayload(**raw_json)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Invalid payload: {e}"}), 400

    new_status = _to_engagement_status(payload.status)
    if new_status is None:
        return jsonify({"status": "error", "message": "Invalid status"}), 400
    if new_status == EngagementStatus.VALIDATED:
        return jsonify({"status": "error", "message": "Forbidden"}), 403
    if current_status == EngagementStatus.CANCELLED:
        return jsonify({"status": "error", "message": "Cannot change status from cancelled"}), 400
    if current_status == EngagementStatus.VALIDATED and new_status != EngagementStatus.CANCELLED:
        return jsonify({"status": "error", "message": "Cannot change status from validated to non-cancelled"}), 400

    try:
        db.update_engagement(engagement_id=engagement_id, status=new_status)
        return jsonify({"status": "success", "message": "Engagement updated"}), 200
    except ValueError:
        return jsonify({"status": "error", "message": "Failed to update engagement"}), 400


@api_bp.route("/engagement/<int:engagement_id>", methods=["DELETE"])
@login_required
def delete_engagement(engagement_id):
    db = get_db()
    engagement = db.get_engagement_by_id(engagement_id)
    if engagement is None:
        return jsonify({"status": "error", "message": "Engagement not found"}), 404
    if engagement.user != current_user:
        return jsonify({"status": "error", "message": "Forbidden"}), 403
    if _to_engagement_status(engagement.status) == EngagementStatus.VALIDATED:
        return jsonify({
            "status": "error",
            "message": "Unauthorized to delete a validated engagement"
        }), 400

    try:
        db.delete_engagement(engagement_id=engagement_id)
        return jsonify({"status": "success", "message": "Engagement deleted successfully"}), 200
    except ValueError:
        return jsonify({"status": "error", "message": "Failed to delete engagement"}), 400