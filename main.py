import re
from flask import Flask, render_template, request, jsonify, redirect, flash, url_for
import pickle
from fuzzywuzzy import fuzz
import urllib3
import json
import stripe
from flask_wtf import FlaskForm
import mysql.connector
from flask_mysqldb import MySQL
from wtforms import StringField, PasswordField, SubmitField, TelField, DateField, IntegerField, EmailField
from wtforms.validators import DataRequired, EqualTo, Email, Length, ValidationError
import requests
import asyncio
import csv
from idlelib import query
import Levenshtein
import smtplib
from email.message import EmailMessage
import os

app = Flask(__name__)

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = os.environ.get("sql_password")
app.config['MYSQL_DB'] = 'project'
app.secret_key = os.environ.get("sql_key")

mysql = MySQL(app)


@app.route("/")
def home():
    place_list = places['name'].tolist()
    return render_template('index.html', place_list=place_list)


popular_df = pickle.load(open('popular2.pkl', 'rb'))
places = pickle.load(open('places_list6.pkl', 'rb'))
similarity = pickle.load(open('similarity6.pkl', 'rb'))


# HOTELS SEARCH
def load_data():
    with open('KNN_hotels_merged.csv', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        data = list(reader)
    return data


# Function to calculate Levenshtein distance
def levenshtein_distance(s1, s2):
    return Levenshtein.distance(s1.lower(), s2.lower())


# Route for searching hotels
@app.route('/hotels_results', methods=['GET', 'POST'])
def hotels_results():
    if request.method == 'POST':
        search_query = request.form['search_query']

        # Check if search query is empty
        if not search_query:
            return render_template('hotels_results.html', message="Please enter a search query.")

        hotels = load_data()  # Assuming load_data() loads hotels from the CSV file
        # Filter hotels based on search query
        filtered_hotels = [hotel for hotel in hotels if search_query.lower() in hotel['name_place'].lower()]
        if filtered_hotels:
            # Calculate Levenshtein distance between search query and hotel names
            results = [(hotel, levenshtein_distance(search_query, hotel['name_place'])) for hotel in filtered_hotels]
            # Sort results based on Levenshtein distance
            results.sort(key=lambda x: x[1])
            # Extract hotel data from sorted results
            precise_results = [hotel[0] for hotel in results]
            return render_template('hotels_results.html', results=precise_results, query=search_query, hotels=hotels)
        else:
            return render_template('hotels_results.html', query=search_query, message="No results found.")
    else:
        return render_template('hotels_results.html')


# RESTAURANTS SEARCH
def load_data2():
    with open('KNN_restaurant_merged.csv', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        data = list(reader)
    return data


def levenshtein_distance2(s1, s2):
    return Levenshtein.distance(s1.lower(), s2.lower())


@app.route('/restaurants_results', methods=['GET', 'POST'])
def restaurants_results():
    if request.method == 'POST':
        search_query2 = request.form['search_query2']

        # Check if search query is empty
        if not search_query2:
            return render_template('restaurants_results.html', message="Please enter a search query.")

        restaurants = load_data2()
        filtered_restaurants = [hotel for hotel in restaurants if search_query2.lower() in hotel['name_place'].lower()]

        if filtered_restaurants:
            resResults = [(restaurant, levenshtein_distance2(search_query2, restaurant['name_place'])) for restaurant in
                          filtered_restaurants]
            resResults.sort(key=lambda x: x[1])
            precise_results = [restaurant[0] for restaurant in resResults]
            return render_template('restaurants_results.html', resResults=precise_results, query2=search_query2,
                                   name_place=['name_place'])
        else:
            return render_template('restaurants_results.html', query2=search_query2, message="No results found.")
    else:
        return render_template('restaurants_results.html')


# POPULAR
@app.route('/popular')
def popular():
    return render_template('popular.html',
                           place_name=list(popular_df['name'].values),
                           address=list(popular_df['address'].values),
                           image=list(popular_df['image'].values),
                           noOfReviews=list(popular_df['numberOfReviews'].values),
                           rating=list(popular_df['rating'].values)
                           )


def get_recommendations(place):
    place_lower = place.lower()
    # Use fuzzy string matching to find the closest match in lowercase titles
    match_scores = [(idx, fuzz.ratio(place_lower, title.lower())) for idx, title in enumerate(places['name'])]
    match_scores.sort(key=lambda x: x[1], reverse=True)
    best_match_idx, best_score = match_scores[0]
    # If the best match is below a certain threshold, consider it as not found
    if best_score < 80:  # Adjust the threshold as needed
        return None, None, None, None, None, None, None, "Sorry, we couldn't find recommendations for '{}'.".format(
            place)

    # Get recommendations based on the best matched title
    idx = best_match_idx
    sim_scores = list(enumerate(similarity[idx]))
    sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)
    sim_scores = sim_scores[:8]
    place_indices = [i[0] for i in sim_scores]
    recommended_place_titles = places['name'].iloc[place_indices].tolist()
    recommended_place_posters = places['image'].iloc[place_indices].tolist()
    recommended_place_address = places['address'].iloc[place_indices].tolist()
    recommended_place_rating = places['rating'].iloc[place_indices].tolist()
    recommended_place_city = places['addressObj.city'].iloc[place_indices].tolist()
    recommended_place_numberOfReviews = places['numberOfReviews'].iloc[place_indices].tolist()
    recommended_place_website = places['webUrl'].iloc[place_indices].tolist()
    return (recommended_place_titles, recommended_place_posters,
            recommended_place_address, recommended_place_rating,
            recommended_place_numberOfReviews, recommended_place_city,
            recommended_place_website, None)


# recommendation page
@app.route('/recommend', methods=['POST'])
def recommend():
    place_title = request.form['selected_place']
    (recommended_place_titles, recommended_place_posters,
     recommended_place_address, recommended_place_rating,
     recommended_place_numberOfReviews, recommended_place_city,
     recommended_place_website, message) = get_recommendations(place_title)

    if message:
        return render_template('recommend.html', message=message)

    return render_template('recommend.html', place_list=places['name'].tolist(),
                           recommended_place_titles=recommended_place_titles,
                           recommended_place_address=recommended_place_address,
                           recommended_place_rating=recommended_place_rating,
                           recommended_place_numberOfReviews=recommended_place_numberOfReviews,
                           recommended_place_city=recommended_place_city,
                           recommended_place_website=recommended_place_website,
                           recommended_place_posters=recommended_place_posters)


# FEEDBACK FORM
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
EMAIL_ADDRESS = os.environ.get("email_id")
EMAIL_PASSWORD = os.environ.get("email_password")


@app.route('/contact')
def contactUs():
    return render_template('contact.html', feedback_submitted=False)


@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    name = request.form['name']
    email = request.form['email']
    feedback = request.form['feedback']

    # Construct email message
    msg = EmailMessage()
    msg['Subject'] = 'Feedback Submission'
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = EMAIL_ADDRESS
    msg.set_content(f'Name: {name}\nEmail: {email}\nFeedback: {feedback}')

    # Send email
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)

    return redirect('/contact')


@app.route("/weatherSearch")
def weatherSearch():
    return render_template("weatherSearch.html")


class LoginForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(min=5, max=15)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8, max=8)])
    submit = SubmitField("Login")


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        name = form.name.data
        password = form.password.data

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE name=%s", (name,))
        mysql.connection.commit()
        cursor.close()

        return render_template('index.html')

    return render_template('login.html', form=form)


def validate_mobile(form, field):
    pattern = r'^[9876]\d{9}$'
    if not re.match(pattern, field.data):
        raise ValidationError('Invalid mobile number')


class signupForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(min=5, max=15)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    mobile = TelField("Mobile", validators=[DataRequired(), Length(min=10, max=10), validate_mobile])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8, max=8)])
    con_password = PasswordField("Confirm Password", validators=[DataRequired(), EqualTo('password',
                                                                                         message="Enter the correct password"), ])
    submit = SubmitField("Register")


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = signupForm()
    if form.validate_on_submit():
        name = form.name.data
        email = form.email.data
        mobile = form.mobile.data
        password = form.password.data

        # store data into database
        cursor = mysql.connection.cursor()
        cursor.execute("INSERT INTO users (name,email,mobile,password) VALUES (%s,%s,%s,%s)",
                       (name, email, mobile, password))
        mysql.connection.commit()
        cursor.close()

        return render_template('index.html')

    return render_template('signup.html', form=form)


# Configure Stripe
stripe.api_key = os.environ.get("api_key")

with open('Price.json', 'r', encoding='utf-8') as f:
    hotel_data = json.load(f)


class BookingForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(min=5, max=15)])
    checkin = DateField('Check_in', validators=[DataRequired()])
    checkout = DateField('Check_out', validators=[DataRequired()])
    room = IntegerField('Room', validators=[DataRequired()])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    mobile = TelField('Mobile', validators=[DataRequired(), Length(min=10, max=10), validate_mobile])
    submit = SubmitField('Book Now')


@app.route('/book', methods=['GET', 'POST'])
def book():
    if request.method == 'GET':
        hotel_name = request.args.get('hotel_name')
        hotel_price = request.args.get('hotel_price')
        return render_template('booking.html', hotel_name=hotel_name, hotel_price=hotel_price)
    elif request.method == 'POST':
        form = BookingForm(request.form)
        if form.validate():
            name = form.name.data
            email = form.email.data
            mobile = form.mobile.data
            check_in = form.checkin.data
            check_out = form.checkout.data
            hotel_name = request.form['hotel_name']
            room = int(request.form['room'])
            total_price = float(request.form['total_price'])

            # Insert the booking details into the database
            cur = mysql.connection.cursor()
            cur.execute(
                "INSERT INTO book (Name, Mobile, Email, Check_in, Check_out, Hotel_name, Room, Total_price) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (name, mobile, email, check_in, check_out, hotel_name, room, total_price))
            mysql.connection.commit()
            cur.close()

            return redirect(url_for('payment'))
        else:
            # Form did not pass validation, render the form again with errors
            hotel_name = request.form.get('hotel_name')
            hotel_price = request.form.get('hotel_price')
            return render_template('booking.html', hotel_name=hotel_name, hotel_price=hotel_price, form=form)


@app.route("/payment", methods=["GET", "POST"])
def payment():
    if request.method == "POST":
        # Process payment here
        amount = 1000  # Amount in INR
        customer = stripe.Customer.create(
            source=request.form["stripeToken"]
        )
        charge = stripe.Charge.create(
            customer=customer.id,
            amount=amount,
            currency="inr",
            description="Booking payment"
        )

        return redirect(url_for('conformation'))
    else:
        return render_template("payment.html")


@app.route('/conformation', methods=['GET', 'POST'])
def conformation():
    # Obtain a cursor object from the database connection
    cursor = mysql.connection.cursor()

    try:
        # Retrieve booking details from the database
        cursor.execute("SELECT * FROM book ORDER BY id DESC LIMIT 1")
        booking = cursor.fetchone()
        if booking:
            return render_template('conformation.html', booking=booking)
        else:
            return "No booking found."
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        # Close the cursor
        cursor.close()


@app.route('/booking_history', methods=['GET' 'POST'])
def booking_history():
    if request.method == 'POST':
        email = request.form['email']
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM booking WHERE email = %s", (email,))
        booking = cur.fetchall()
        cur.close()
        return render_template('booking_history.html', booking=booking)
    else:
        return ('BOOKING NOT FOUND')


class ReservationForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(min=5, max=25)])
    mobile = StringField('Mobile', validators=[DataRequired(), Length(min=10, max=10)])
    date = DateField('Date', validators=[DataRequired()])
    num_people = IntegerField('Number of People', validators=[DataRequired()])
    submit = SubmitField('Reserve')


@app.route('/reserve', methods=['GET', 'POST'])
def reserve():
    restaurant_name = request.form.get('restaurant_name')  # Extract restaurant name from form data
    form = ReservationForm()
    if form.validate_on_submit():
        name = form.name.data
        mobile = form.mobile.data
        date = form.date.data
        num_people = form.num_people.data
        num_tables = num_people // 4 + (1 if num_people % 4 else 0)  # Calculate number of tables

        # Insert the booking details into the database
        cur = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO reservations (name, mobile, date, people, tables, restaurant) VALUES (%s, %s, %s, %s, %s, %s)",
            (name, mobile, date, num_people, num_tables, restaurant_name))
        mysql.connection.commit()
        cur.close()

        return redirect(url_for('conf'))
    return render_template('reserve.html', form=form)


@app.route('/conf', methods=['GET', 'POST'])
def conf():
    # Obtain a cursor object from the database connection
    cursor = mysql.connection.cursor()

    try:
        # Retrieve booking details from the database
        cursor.execute("SELECT * FROM reservations ORDER BY id DESC LIMIT 1")
        reserve = cursor.fetchone()
        if reserve:
            return render_template('conf.html', reserve=reserve)
        else:
            return "No reservetion found."
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        # Close the cursor
        cursor.close()


if __name__ == "__main__":
    app.run(debug=True)
