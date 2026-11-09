import os
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-this-secret")
db_url = os.environ.get("DATABASE_URL", "sqlite:///flaxxi_esports.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(40), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class Tournament(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    game = db.Column(db.String(30), nullable=False)
    mode = db.Column(db.String(20), nullable=False)
    map_name = db.Column(db.String(50), default="—")
    entry_type = db.Column(db.String(20), default="Free")
    prize_pool = db.Column(db.String(60), default="TBA")
    slots = db.Column(db.Integer, default=48)
    match_time = db.Column(db.String(80), nullable=False)
    status = db.Column(db.String(20), default="upcoming")
    description = db.Column(db.Text, default="")
    room_id = db.Column(db.String(80), default="")
    room_password = db.Column(db.String(80), default="")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class Registration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    tournament_id = db.Column(db.Integer, db.ForeignKey("tournament.id"), nullable=False)
    player_name = db.Column(db.String(60), nullable=False)
    game_uid = db.Column(db.String(60), nullable=False)
    team_name = db.Column(db.String(60), default="")
    status = db.Column(db.String(20), default="pending")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user = db.relationship("User", backref="registrations")
    tournament = db.relationship("Tournament", backref="registrations")
    __table_args__ = (db.UniqueConstraint("user_id", "tournament_id", name="unique_user_tournament"),)

class Winner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey("tournament.id"), nullable=False)
    player_or_team = db.Column(db.String(80), nullable=False)
    position = db.Column(db.Integer, nullable=False)
    prize = db.Column(db.String(60), default="")
    tournament = db.relationship("Tournament", backref="winners")

def current_user():
    uid = session.get("user_id")
    return db.session.get(User, uid) if uid else None

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            flash("Please sign in first.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Admin access required.", "warning")
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapper

@app.context_processor
def inject_globals():
    return {"current_user": current_user(), "is_admin": session.get("is_admin", False)}

@app.route("/")
def index():
    tournaments = Tournament.query.order_by(Tournament.created_at.desc()).all()
    return render_template("index.html", tournaments=tournaments)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if len(username) < 3 or len(password) < 8 or "@" not in email:
            flash("Username must be 3+ characters, valid email, and password 8+ characters.", "danger")
        elif User.query.filter((User.username == username) | (User.email == email)).first():
            flash("Username or email already exists.", "danger")
        else:
            user = User(username=username, email=email, password_hash=generate_password_hash(password))
            db.session.add(user); db.session.commit()
            session["user_id"] = user.id
            flash("Account created. Welcome to FLAXXI ESPORTS!", "success")
            return redirect(url_for("index"))
    return render_template("auth.html", mode="register")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identity = request.form.get("identity", "").strip().lower()
        user = User.query.filter((db.func.lower(User.email) == identity) | (db.func.lower(User.username) == identity)).first()
        if user and check_password_hash(user.password_hash, request.form.get("password", "")):
            session.clear(); session["user_id"] = user.id
            flash("Signed in successfully.", "success")
            return redirect(url_for("index"))
        flash("Invalid username/email or password.", "danger")
    return render_template("auth.html", mode="login")

@app.route("/logout")
def logout():
    session.clear()
    flash("You are signed out.", "info")
    return redirect(url_for("index"))

@app.route("/tournament/<int:tournament_id>")
def tournament_detail(tournament_id):
    t = db.get_or_404(Tournament, tournament_id)
    regs = Registration.query.filter_by(tournament_id=t.id, status="approved").count()
    my_reg = Registration.query.filter_by(tournament_id=t.id, user_id=current_user().id).first() if current_user() else None
    return render_template("tournament.html", t=t, approved_count=regs, my_reg=my_reg)

@app.route("/tournament/<int:tournament_id>/join", methods=["POST"])
@login_required
def join_tournament(tournament_id):
    t = db.get_or_404(Tournament, tournament_id)
    if t.status != "upcoming":
        flash("Registration is closed for this tournament.", "warning")
    elif Registration.query.filter_by(user_id=current_user().id, tournament_id=t.id).first():
        flash("You have already submitted a registration.", "info")
    elif Registration.query.filter_by(tournament_id=t.id, status="approved").count() >= t.slots:
        flash("All slots are full.", "danger")
    else:
        player = request.form.get("player_name", "").strip()
        uid = request.form.get("game_uid", "").strip()
        team = request.form.get("team_name", "").strip()
        if not player or not uid:
            flash("In-game name and game UID are required.", "danger")
        else:
            db.session.add(Registration(user_id=current_user().id, tournament_id=t.id, player_name=player, game_uid=uid, team_name=team))
            db.session.commit()
            flash("Registration submitted. Wait for admin approval.", "success")
    return redirect(url_for("tournament_detail", tournament_id=t.id))

@app.route("/my-tournaments")
@login_required
def my_tournaments():
    return render_template("my_tournaments.html", registrations=current_user().registrations)

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = os.environ.get("ADMIN_USERNAME", "admin")
        password = os.environ.get("ADMIN_PASSWORD", "")
        if password and request.form.get("username") == username and check_password_hash(generate_password_hash(password), request.form.get("password", "")):
            session.clear(); session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Admin credentials incorrect or ADMIN_PASSWORD is not configured.", "danger")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/admin")
@admin_required
def admin_dashboard():
    return render_template("admin.html",
        tournaments=Tournament.query.order_by(Tournament.created_at.desc()).all(),
        registrations=Registration.query.order_by(Registration.created_at.desc()).all(),
        users=User.query.count())

@app.route("/admin/tournament/create", methods=["POST"])
@admin_required
def create_tournament():
    title = request.form.get("title", "").strip()
    game = request.form.get("game", "")
    mode = request.form.get("mode", "")
    match_time = request.form.get("match_time", "").strip()
    if not title or game not in ("Free Fire", "PUBG Mobile") or mode not in ("Solo", "Duo", "Squad") or not match_time:
        flash("Please complete the required tournament fields.", "danger")
    else:
        t = Tournament(title=title, game=game, mode=mode, map_name=request.form.get("map_name","").strip(),
            entry_type="Free", prize_pool=request.form.get("prize_pool","TBA").strip()[:60],
            slots=max(1, min(int(request.form.get("slots", 48) or 48), 500)),
            match_time=match_time, description=request.form.get("description","").strip())
        db.session.add(t); db.session.commit()
        flash("Tournament published.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/registration/<int:registration_id>/<action>", methods=["POST"])
@admin_required
def review_registration(registration_id, action):
    r = db.get_or_404(Registration, registration_id)
    if action not in ("approve", "reject"):
        abort(400)
    if action == "approve":
        approved = Registration.query.filter_by(tournament_id=r.tournament_id, status="approved").count()
        if approved >= r.tournament.slots:
            flash("No slots left to approve this player.", "danger")
            return redirect(url_for("admin_dashboard"))
        r.status = "approved"
    else:
        r.status = "rejected"
    db.session.commit()
    flash(f"Registration {action}d.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/tournament/<int:tournament_id>/room", methods=["POST"])
@admin_required
def update_room(tournament_id):
    t = db.get_or_404(Tournament, tournament_id)
    t.room_id = request.form.get("room_id","").strip()
    t.room_password = request.form.get("room_password","").strip()
    t.status = request.form.get("status", "upcoming")
    db.session.commit()
    flash("Match room and status updated.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/tournament/<int:tournament_id>/winner", methods=["POST"])
@admin_required
def add_winner(tournament_id):
    t = db.get_or_404(Tournament, tournament_id)
    name = request.form.get("player_or_team","").strip()
    try:
        position = int(request.form.get("position", "1"))
    except ValueError:
        position = 0
    if name and 1 <= position <= 100:
        db.session.add(Winner(tournament_id=t.id, player_or_team=name, position=position, prize=request.form.get("prize","").strip()))
        db.session.commit()
        flash("Winner added.", "success")
    else:
        flash("Enter a winner name and valid position.", "danger")
    return redirect(url_for("admin_dashboard"))

@app.route("/leaderboard")
def leaderboard():
    winners = Winner.query.join(Tournament).order_by(Winner.position.asc()).all()
    return render_template("leaderboard.html", winners=winners)

with app.app_context():
    db.create_all()
    # Add demo events only on a brand-new database.
    if Tournament.query.count() == 0:
        db.session.add_all([
            Tournament(title="Neon Clash Open", game="Free Fire", mode="Squad", map_name="Bermuda", prize_pool="Community prize", slots=48, match_time="Schedule announced soon", description="Open community tournament. Follow the rules and wait for approval."),
            Tournament(title="Battle Royale Cup", game="PUBG Mobile", mode="Duo", map_name="Erangel", prize_pool="Community prize", slots=32, match_time="Schedule announced soon", description="Fair-play duo event for the community.")
        ])
        db.session.commit()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
