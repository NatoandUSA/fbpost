"""API Blueprint for Automation Jobs and Background Execution.
Decouples subprocess lifecycle from HTTP connection.
"""

from flask import Blueprint, jsonify, request, Response
from services.job_manager import JobManager

jobs_bp = Blueprint("jobs", __name__)
job_manager = JobManager()
ALLOWED_JOB_COMMANDS = {"auth", "group", "page", "thread", "interact", "scrape", "comment", "join-group", "create-page", "reconcile-post"}



@jobs_bp.route("/api/jobs", methods=["POST"])
def submit_job():
    data = request.get_json(silent=True) or {}
    command = data.get("command")
    if not command:
        return jsonify({"success": False, "error": "Command is required"}), 400
    if command not in ALLOWED_JOB_COMMANDS:
        return jsonify({"success": False, "error": "Unsupported command"}), 400

    account_id = data.get("accountId")
    job_id = job_manager.submit_job(command, data, account_id=account_id)
    return jsonify({
        "success": True,
        "job_id": job_id,
        "status": "queued",
        "message": f"Job {job_id} đã được đưa vào hàng đợi.",
    }), 201


@jobs_bp.route("/api/jobs", methods=["GET"])
def list_jobs():
    try:
        limit = max(1, min(int(request.args.get("limit", 50)), 200))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "limit must be an integer"}), 400
    state = request.args.get("state")
    jobs = job_manager.list_jobs(limit=limit, state=state)
    return jsonify({
        "success": True,
        "jobs": jobs,
        "total": len(jobs),
        "active_job_id": job_manager.get_active_job_id(),
    })


@jobs_bp.route("/api/jobs/active", methods=["GET"])
def get_active_job():
    active_id = job_manager.get_active_job_id()
    if not active_id:
        return jsonify({"success": True, "active": False, "job": None})
    job = job_manager.get_job(active_id)
    return jsonify({"success": True, "active": True, "job": job})


import re

def is_valid_job_id(job_id: str) -> bool:
    return bool(re.match(r"^[0-9a-zA-Z_\-]+$", job_id)) and ".." not in job_id


@jobs_bp.route("/api/jobs/<job_id>", methods=["GET"])
def get_job(job_id):
    if not is_valid_job_id(job_id):
        return jsonify({"success": False, "error": "Invalid job_id format"}), 400
    job = job_manager.get_job(job_id)
    if not job:
        return jsonify({"success": False, "error": "Job not found"}), 404
    return jsonify({
        "success": True,
        "job": job,
    })


@jobs_bp.route("/api/jobs/<job_id>/logs", methods=["GET"])
def get_job_logs(job_id):
    if not is_valid_job_id(job_id):
        return jsonify({"success": False, "error": "Invalid job_id format"}), 400
    if not job_manager.get_job(job_id):
        return jsonify({"success": False, "error": "Job not found"}), 404
    stream_mode = request.args.get("stream", "").lower() in ("1", "true", "yes")
    if stream_mode:
        return Response(job_manager.subscribe_logs(job_id), mimetype="text/plain; charset=utf-8")

    try:
        offset = max(0, int(request.args.get("offset", 0)))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "offset must be a non-negative integer"}), 400
    logs = job_manager.get_job_logs(job_id, offset=offset)
    return jsonify({
        "success": True,
        "job_id": job_id,
        "logs": logs,
    })


@jobs_bp.route("/api/jobs/<job_id>/cancel", methods=["POST"])
def cancel_job(job_id):
    if not is_valid_job_id(job_id):
        return jsonify({"success": False, "error": "Invalid job_id format"}), 400
    job = job_manager.get_job(job_id)
    if not job:
        return jsonify({"success": False, "error": "Job not found"}), 404

    job_manager.cancel_job(job_id)
    return jsonify({
        "success": True,
        "message": f"Tiến trình {job_id} đã được hủy bỏ thành công.",
    })


@jobs_bp.route("/api/cancel", methods=["POST"])
def cancel_active():
    cancelled = job_manager.cancel_active_job()
    if cancelled:
        return jsonify({"success": True, "message": "Đã gửi tín hiệu dừng tiến trình đang chạy."})
    return jsonify({"success": False, "message": "Hiện không có tiến trình nào đang hoạt động."})


@jobs_bp.route("/api/run", methods=["POST"])
def run_streaming():
    """Backward-compatible endpoint: submits job to JobManager and streams output."""
    data = request.get_json(silent=True) or {}
    cmd = data.get("command")
    if not cmd:
        def _err():
            yield "Error: Command is required.\nRUN_RESULT:failed\n"
        return Response(_err(), mimetype="text/plain; charset=utf-8")
    if cmd not in ALLOWED_JOB_COMMANDS:
        def _unsupported():
            yield "Error: Unsupported command.\nRUN_RESULT:failed\n"
        return Response(_unsupported(), mimetype="text/plain; charset=utf-8")

    account_id = data.get("accountId")
    job_id = job_manager.submit_job(cmd, data, account_id=account_id)

    def _stream():
        try:
            yield f"JOB_ID:{job_id}\n"
            for line in job_manager.subscribe_logs(job_id):
                yield line
        except Exception as e:
            yield f"\n❌ [Streaming Error]: {e}\nRUN_RESULT:failed\n"

    return Response(_stream(), mimetype="text/plain; charset=utf-8")
