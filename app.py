from flask import Flask, render_template, request, session, redirect, url_for, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
import openai
from recipes_data import recipes  # Ensure this file exists with a 'recipes' dictionary

# ========== Configuration ==========
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.secret_key = 'supersecretkey'
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
admin = Admin(app, name='Recipe Admin', template_mode='bootstrap3')

# ========== OpenAI API Key ==========
openai.api_key = "your-openai-key"  # Replace with your actual OpenAI API key

# ========== Models ==========
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(150), nullable=False)

admin.add_view(ModelView(User, db.session))

# ========== Routes ==========

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        try:
            username = request.form["email"]
            password = request.form["password"]
            confirm_password = request.form["confirm_password"]
            if password != confirm_password:
                flash("Passwords do not match!", "danger")
                return redirect(url_for("signup"))
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                flash("Username already exists! Please choose a different one.", "danger")
                return redirect(url_for("signup"))
            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
            new_user = User(username=username, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            flash("Account created successfully! You can now log in.", "success")
            return redirect(url_for("login"))
        except KeyError as e:
            flash(f"Form error: Missing key {str(e)}", "danger")
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        try:
            username = request.form["email"]
            password = request.form["password"]
            user = User.query.filter_by(username=username).first()
            if user and bcrypt.check_password_hash(user.password, password):
                session["user_id"] = user.id
                return redirect(url_for("home"))
            else:
                flash("Login failed. Check your username and/or password", "danger")
        except KeyError as e:
            flash(f"Form error: Missing key {str(e)}", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("home"))

@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))
    query = request.args.get("search", "").lower()
    filtered_recipes = {
        category: {
            food_type: {
                food: details for food, details in foods.items() if query in food.lower()
            }
            for food_type, foods in types.items()
            if any(query in food.lower() for food in foods)
        }
        for category, types in recipes.items()
        if any(query in food.lower() for food_type in types.values() for food in food_type)
    } if query else recipes
    return render_template("index.html", recipes=filtered_recipes, search_query=query, categories=recipes.keys())

# ---------- Region Select ----------
@app.route("/region/<category>")
def region(category):
    if category not in recipes:
        return "Category not found", 404
    return render_template("region_type.html", category=category, recipes=recipes)


# ---------- Veg / Non-Veg ----------
@app.route("/recipes/<category>/<food_type>")
def recipes_by_type(category, food_type):
    if category not in recipes or food_type not in recipes[category]:
        return "Recipes not found", 404
    filtered_recipes = recipes[category][food_type]
    return render_template("recipes_list.html", category=category, food_type=food_type, recipes=filtered_recipes)

# ---------- Individual Recipe ----------
@app.route("/recipe/<category>/<food>")
def recipe(category, food):
    for food_type in recipes.get(category, {}):
        if food in recipes[category][food_type]:
            return render_template("recipe.html", category=category, food=food, details=recipes[category][food_type][food])
    return "Recipe not found", 404

@app.route("/search_suggestions")
def search_suggestions():
    query = request.args.get('query', '').lower()
    suggestions = [
        food for category in recipes.values()
        for type_dict in category.values()
        for food in type_dict
        if query in food.lower()
    ]
    return jsonify(suggestions)

@app.route('/search')
def search():
    query = request.args.get('query', '').lower()
    matching_recipes = {
        category: {
            food_type: {
                food: details for food, details in foods.items() if query in food.lower()
            }
            for food_type, foods in type_dict.items()
            if any(query in food.lower() for food in foods)
        }
        for category, type_dict in recipes.items()
        if any(query in food.lower() for foods in type_dict.values() for food in foods)
    }
    return render_template('search_results.html', query=query, recipes=matching_recipes)

# ====== AI Recipe Generation ======
@app.route("/generate_recipe", methods=["GET", "POST"])
def generate_recipe():
    if "user_id" not in session:
        return redirect(url_for("login"))

    ai_recipe = None

    if request.method == "POST":
        prompt = request.form["prompt"]
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful AI chef who creates detailed Indian recipes."},
                    {"role": "user", "content": prompt}
                ]
            )
            ai_recipe = response['choices'][0]['message']['content']
        except Exception as e:
            flash(f"Error generating recipe: {str(e)}", "danger")

    return render_template("generate_recipe.html", ai_recipe=ai_recipe)

# ========== Run App ==========
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
