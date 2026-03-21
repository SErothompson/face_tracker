"""Custom error handlers for production-safe error pages."""

from flask import render_template


def register_error_handlers(app):
    """Register custom error page handlers."""

    @app.errorhandler(400)
    def bad_request(e):
        return render_template("errors/error.html", code=400, message="Bad Request"), 400

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/error.html", code=403, message="Access Denied"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/error.html", code=404, message="Page Not Found"), 404

    @app.errorhandler(429)
    def too_many_requests(e):
        return render_template("errors/error.html", code=429, message="Too Many Requests"), 429

    @app.errorhandler(500)
    def internal_error(e):
        return render_template("errors/error.html", code=500, message="Internal Server Error"), 500
