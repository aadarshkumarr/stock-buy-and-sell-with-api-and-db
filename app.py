import os
from symtable import Symbol
from tkinter import EXCEPTION, N
from datetime import datetime

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd


# Configure application
app = Flask(__name__)
os.environ["API_KEY"]="pk_4e98863961804c81a97d4052d11a6d33"
#os.environ["API_KEY"]="L0XBoCcvp2So7sI37HN30x1tjhKXwh5N"

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database and ensure the purchases table exists
db = SQL("sqlite:///finance.db")

# Create a separate database for purchases
try:
    db.execute("SELECT * FROM purchases")
except:
    db.execute('CREATE TABLE purchases (id INTEGER NOT NULL, symbol TEXT NOT NULL , shares INTEGER NOT NULL)')

# Create a separate database for history
try:
    db.execute("SELECT * FROM history")
except:
    db.execute('CREATE TABLE history (id INTEGER NOT NULL, symbol TEXT NOT NULL , shares TEXT NOT NULL, price TEXT NOT NULL, date TEXT)')

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    package = db.execute("SELECT symbol, shares FROM purchases WHERE id=?", session['user_id'])
    grandTotal = 0

    # Parsing the data to create a package to send over to jinja. Going over each stock dictionary and add necessary data into it. 
    for stock in package:
        data = lookup(stock['symbol'])
        stock['name'] = data['name']
        stock['price'] = data['price']
        total = float(stock['price'])*stock['shares']
        stock['total'] = usd(total)
        grandTotal += total
    
    
    balance = float(db.execute("SELECT cash FROM users WHERE id=?", session['user_id'])[0]['cash'])
    grandTotal += balance
    return render_template('index.html', package=package, balance=usd(balance), grandTotal=usd(grandTotal))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")

    symbol = request.form.get('symbol').upper()
    data = lookup(symbol)

    #Data checking
    if not symbol:
        return apology("Please enter a stock's symbol", 400)
    if not data:
        return apology("Please enter a valid stock's symbol", 400)

    number_of_shares = request.form.get('shares')
    if not number_of_shares.isnumeric():
        return apology("Please enter a valid number of shares", 400)

    number_of_shares = int(number_of_shares)

    if number_of_shares < 1:
        return apology("Please enter a valid number of shares",400)
    
    balance = db.execute('SELECT cash FROM users WHERE id=?', session['user_id'])[0]['cash']
    price = float(data['price'])
    cost = number_of_shares * price

    if cost > float(balance):
        return apology("You are poor :)", 400)

    #Entering the data into the database, try/except in case the owner already has some stock then the buy would add to the total stock value instead of writing separate entry
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if db.execute("SELECT * FROM purchases WHERE id=? AND symbol=?", session['user_id'], symbol):
        #Update the purchases database
        db.execute("UPDATE purchases SET shares = shares + ? WHERE symbol=? AND id=?", number_of_shares, symbol, session['user_id'])
    else:
        #Insert a new stock into purchases database
        db.execute("INSERT INTO purchases (id, symbol, shares) VALUES (?, ?, ?)", session['user_id'], symbol, number_of_shares)
    #Insert into the history database for record
    db.execute("INSERT INTO history (id, symbol, shares, price, date) VALUES (?, ?, ?, ?, ?)", session['user_id'], symbol, f'+{number_of_shares}', usd(price), now)
    #Update the cash on the user
    db.execute("UPDATE users SET cash = cash - ? WHERE id=?", cost, session['user_id'])
        
    return redirect("/")
    # return render_template("buy.html", success="Succeed")

        


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    package = db.execute("SELECT * FROM history WHERE id=?", session['user_id'])
    return render_template('history.html', package=package[::-1])


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get('symbol')
        if not symbol:
            return apology("Please enter a Symbol", 400)
        data = lookup(symbol)
        if not data or data == None:
            return apology("Please enter a valid stock", 400)
        
        data['price'] = usd(data['price'])
        return render_template('quoted.html', data=data)

    return render_template('quote.html')


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_pw = request.form.get('confirmation')

        #Data checking
        if not username:
            print(username)
            return apology('Please enter a username', 400)
            # return render_template("register.html", error='Please enter a username')

        #Check if the user already exists
        if db.execute("SELECT username FROM users WHERE username=?", username):
            return apology('Username already exists', 400)
            # return render_template("register.html", error=f"The username already exists, please login <a href='{url_for('login')}'>here</a>.")

        if not password:
            return apology('Please enter a password', 400)
            return render_template("register.html", error='Please enter a password')
        if confirm_pw != password:
            return apology('Password mismatch', 400)
            # return render_template("register.html", error='The password does not match')
        
        hash = generate_password_hash(password)
        
        db.execute('INSERT INTO users (username, hash) VALUES (?, ?)', username, hash)
        return render_template("register.html", success=f"Succeed, you can now login <a href='{url_for('login')}'>here</a>.")


    return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    # Display the webpage 
    if request.method == "GET":
        package = db.execute("SELECT symbol FROM purchases WHERE id=?", session['user_id'])
        data = []
        for stock in package:
            data.append(stock['symbol'])
        return render_template('sell.html', data=data)

    # Process when the user submit a POST request
    symbol = request.form.get('symbol')
    if not symbol:
        return apology("Please choose a stock", 400)

    shares_owned = db.execute("SELECT shares FROM purchases WHERE id=? AND symbol=?", session['user_id'], symbol)
    if not shares_owned:
        return apology("Please enter a valid number of share to sell", 400)

    shares_to_sale = request.form.get('shares')
    shares_owned = int(shares_owned[0]['shares'])
    if not shares_to_sale.isnumeric() or shares_owned < int(shares_to_sale):
        return apology("PLease enter a valid number of share to sell", 400)
    shares_to_sale = int(shares_to_sale)

    #Entering the data into the database, as well as record the history and add the money back to the user
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    price = lookup(symbol)['price']
    cost = shares_to_sale * price

    #Determine if the user wants to sell all of his/her share
    if shares_to_sale == shares_owned:
        db.execute("DELETE FROM purchases WHERE id=? AND symbol=?", session['user_id'], symbol)
    #Update the purchases database
    else:
        db.execute("UPDATE purchases SET shares = shares - ? WHERE symbol=? AND id=?", shares_to_sale, symbol, session['user_id'])
    #Insert into the history database for record
    db.execute("INSERT INTO history (id, symbol, shares, price, date) VALUES (?, ?, ?, ?, ?)", session['user_id'], symbol, f'-{shares_to_sale}', usd(price), now)
    #Update the cash on the user
    db.execute("UPDATE users SET cash = cash + ? WHERE id=?", cost, session['user_id'])

    return redirect('/')
    # return render_template('sell.html', success='Succeed')

    

    

