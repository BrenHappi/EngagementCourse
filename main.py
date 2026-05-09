from engagement_course.app import create_app
import argparse

if __name__ == "__main__":
    app = create_app()
    args = argparse.ArgumentParser()
    port = args.add_argument("--port", type=int, default=3000, help="Port to run the server on")
    args = args.parse_args()

    app.run(host="localhost", port=args.port, debug=True)