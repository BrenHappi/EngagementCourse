from flask import Blueprint, current_app, request, abort, jsonify, flash
from flask_login import current_user, login_required
from datetime import datetime
from engagement_course.models import RaceFilter, Category, CATEGORIES, EngagementStatus
from engagement_course.config import FFC_CALENDAR_URLS, DATE_FORMAT
from pydantic import BaseModel, Field
from engagement_course.utils import get_db

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")


class CreateEngagementPayload(BaseModel):
    user_id: int = Field(gt=0)
    race_id: int = Field(gt=0)
    status: EngagementStatus

class UpdateEngagementPayload(BaseModel):
    status: EngagementStatus


@api_bp.route("/engagement", methods=["POST"])
@login_required
def create_engagement():
    db = get_db()

    raw_json = request.get_json()
    try:
        payload = CreateEngagementPayload(**raw_json)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Invalid payload: {e}"}), 400

    form_user_id = payload.user_id
    if form_user_id != current_user.user_id:
        return jsonify({"status": "error", "message": "Forbidden"}), 403

    race_id = payload.race_id
    race = db.get_race_by_id(race_id)
    if race is None:
        return jsonify({"status": "error", "message": "Race not found"}), 404
    # TODO: check if user can engage (category, date, etc.)
    # TODO: check category compatibility (e.g., access4 trying to engage in open1)

    status = payload.status
    if status not in EngagementStatus.__members__.values():
        return jsonify({"status": "error", "message": "Invalid status"}), 400
    if status == EngagementStatus.VALIDATED:
        return jsonify({"status": "error", "message": "Forbidden"}), 403

    try:
        db.create_engagement(user_id=current_user.id, race=race, status=status)
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
        "id": engagement.id,
        "user_id": engagement.user.user_id,
        "race_id": engagement.race.race_id,
        "status": engagement.status.name
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
    
    current_status = engagement.status

    raw_json = request.get_json()
    try:
        payload = UpdateEngagementPayload(**raw_json)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Invalid payload: {e}"}), 400

    new_status = payload.status
    if new_status not in EngagementStatus.__members__.values():
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
    if engagement.status == EngagementStatus.VALIDATED.value:
        return jsonify({
            "status": "error",
            "message": "Unauthorized to delete a validated engagement"
        }), 400

    try:
        db.delete_engagement(engagement_id=engagement_id)
        return jsonify({"status": "success", "message": "Engagement deleted successfully"}), 200
    except ValueError:
        return jsonify({"status": "error", "message": "Failed to delete engagement"}), 400