from flask import Flask, render_template, request, make_response, redirect, jsonify
from mongita import MongitaClientDisk
from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime


from passwords import hash_password  # (password) -> hashed_password, salt
from passwords import check_password # (password, saved_hashed_password, salt):

app = Flask(__name__)

# create a mongita client connection
client = MongitaClientDisk()

# open the quotes database
quotes_db = client.quotes_db
session_db = client.session_db
user_db = client.user_db

quotes_collection = quotes_db.quotes_collection
comments_collection = quotes_db.comments_collection

import uuid

@app.route("/", methods=["GET"])
@app.route("/quotes", methods=["GET"])
def get_quotes():
    session_id = request.cookies.get("session_id", None)
    if not session_id:
        return redirect("/login")
    
    session_collection = session_db.session_collection
    session_data = session_collection.find_one({"session_id": session_id})
    if not session_data:
        return redirect("/logout")

    user = session_data["user"]
    quotes_collection = quotes_db.quotes_collection
    # Fetch user's own quotes
    my_quotes = list(quotes_collection.find({"owner": user}))
    # Fetch public quotes
    public_quotes = list(quotes_collection.find({"public": True}))

    for quote in my_quotes + public_quotes:
        quote["_id"] = str(quote["_id"])

    return render_template("quotes.html", my_quotes=my_quotes, public_quotes=public_quotes, user=user)
    response = make_response(html)
    response.set_cookie("session_id", session_id)
    return response

@app.route("/login", methods=["GET"])
def get_login():
    session_id = request.cookies.get("session_id", None)
    print("Pre-login session id = ", session_id)
    if session_id:
        return redirect("/quotes")
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def post_login():
    user = request.form.get("user", "")
    password = request.form.get("password", "")
    # open the user collection
    user_collection = user_db.user_collection
    # look for the user
    user_data = list(user_collection.find({"user": user}))
    print(user_data)
    if len(user_data) != 1:
        response = redirect("/login")
        response.delete_cookie("session_id")
        return response
    hashed_password = user_data[0].get("hashed_password","")
    salt = user_data[0].get("salt", "")
    if check_password(password, hashed_password, salt) == False:
        response = redirect("/login")
        response.delete_cookie("session_id")
        return response
    session_id = str(uuid.uuid4())
    # open the session collection
    session_collection = session_db.session_collection
    # insert the user
    session_collection.delete_one({"session_id": session_id})
    session_data = {"session_id": session_id, "user": user}
    session_collection.insert_one(session_data)
    response = redirect("/quotes")
    response.set_cookie("session_id", session_id)
    return response


@app.route("/register", methods=["GET"])
def get_register():
    session_id = request.cookies.get("session_id", None)
    print("Pre-login session id = ", session_id)
    if session_id:
        return redirect("/quotes")
    return render_template("register.html")


@app.route("/register", methods=["POST"])
def post_register():
    user = request.form.get("user", "")
    password = request.form.get("password", "")
    password2 = request.form.get("password2", "")
    if password != password2:
        response = redirect("/register")
        response.delete_cookie("session_id")
        return response
    # open the user collection
    user_collection = user_db.user_collection
    # look for the user
    user_data = list(user_collection.find({"user": user}))
    if len(user_data) == 0:
        hashed_password, salt = hash_password(password)
        user_data = {"user": user, "hashed_password": hashed_password, "salt": salt}
        user_collection.insert_one(user_data)
    response = redirect("/login")
    response.delete_cookie("session_id")
    return response


@app.route("/logout", methods=["GET"])
def get_logout():
    # get the session id
    session_id = request.cookies.get("session_id", None)
    if session_id:
        # open the session collection
        session_collection = session_db.session_collection
        # delete the session
        session_collection.delete_one({"session_id": session_id})
    response = redirect("/login")
    response.delete_cookie("session_id")
    return response


@app.route("/add", methods=["GET"])
def get_add():
    session_id = request.cookies.get("session_id", None)
    if not session_id:
        response = redirect("/login")
        return response
    return render_template("add_quote.html")


@app.route('/api/add_quote', methods=['POST'])
def api_add_quote():
    session_id = request.cookies.get("session_id")
    print("Session ID received:", session_id) 
    if not session_id:
        return jsonify({"success": False, "error": "Unauthorized - No Session"}), 401

    session_data = session_db.session_collection.find_one({"session_id": session_id})
    print("Session data found:", session_data)
    if not session_data:
        return jsonify({"success": False, "error": "Session not found"}), 401

    user = session_data["user"]
    data = request.get_json()
    print("Data received from client:", data) 
    text = data.get("text", "").strip()
    author = data.get("author", "").strip()
    public = data.get("public", False)
    disable_comments = data.get("disable_comments", False)

    if text and author:
        quote = {
            "owner": user,
            "text": text,
            "author": author,
            "public": public,
            "disable_comments": disable_comments,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        data = request.get_json()
        print("Received data:", data)
        
        quotes_collection.insert_one(quote)
        # print("Quote added:", quote)  # debug
        return jsonify({"success": True, "quote": quote})
    else:
        # print("Missing information in data") #debug
        return jsonify({"success": False, "error": "Missing information"}), 400

@app.route("/edit/<id>", methods=["GET"])
def get_edit(id=None):
    session_id = request.cookies.get("session_id", None)
    if not session_id:
        response = redirect("/login")
        return response
    if id:
        # open the quotes collection
        quotes_collection = quotes_db.quotes_collection
        # get the item
        data = quotes_collection.find_one({"_id": ObjectId(id)})
        data["id"] = str(data["_id"])
        return render_template("edit_quote.html", data=data)
    # return to the quotes page
    return redirect("/quotes")


@app.route("/edit", methods=["POST"])
def post_edit():
    session_id = request.cookies.get("session_id", None)
    if not session_id:
        response = redirect("/login")
        return response
    _id = request.form.get("_id", None)
    text = request.form.get("text", "").strip()
    author = request.form.get("author", "")
    if _id:
        # open the quotes collection
        quotes_collection = quotes_db.quotes_collection
        # update the values in this particular record
        values = {"$set": {"text": text, "author": author}}
        data = quotes_collection.update_one({"_id": ObjectId(_id)}, values)
    # do a redirect('....')
    return redirect("/quotes")


@app.route("/delete", methods=["GET"])
@app.route("/delete/<id>", methods=["GET"])
def get_delete(id=None):
    session_id = request.cookies.get("session_id", None)
    if not session_id:
        response = redirect("/login")
        return response
    
    if id:
        session_collection = session_db.session_collection
        session_data = session_collection.find_one({"session_id": session_id})
        if not session_data:
            return redirect("/logout")
        
        user = session_data['user']
        quotes_collection = quotes_db.quotes_collection

        # open the quotes collection
        quote = quotes_collection.find_one({"_id": ObjectId(id)})
        # check if owner
        if quote and quote['owner'] == user:
            # delete the item
            quotes_collection.delete_one({"_id": ObjectId(id)})
        else:
            return redirect("/quotes") 
    return redirect("/quotes")    

@app.route('/search')
def search():
    search_term = request.args.get('search_term', '').strip()
    # print(f"Received search term: {search_term}")  # debug

    if not search_term:
        return redirect("/quotes")
    
    session_id = request.cookies.get("session_id", None)
    session_collection = session_db.session_collection
    session_data = session_collection.find_one({"session_id": session_id})

    if session_data is None:
        return redirect("/login")

    user = session_data['user']
   # print(f"Searching for user: {user}")  # debug 

    data = list(quotes_collection.find({"public": True}))
    
    filtered_data = [quote for quote in data if search_term.lower() in quote.get("text", "").lower()]

   # print(f"Found {len(filtered_data)} items")  # debug output

    for item in filtered_data:
        item["_id"] = str(item["_id"])

    return render_template('quotes.html', data=filtered_data, user=user)

@app.route('/add_comment/<quote_id>', methods=['POST'])
def add_comment(quote_id):
    session_id = request.cookies.get("session_id", None)
    session_data = session_db.session_collection.find_one({"session_id": session_id})
    if not session_data:
        return redirect("/login")

    user = session_data['user']
    quote = quotes_collection.find_one({"_id": ObjectId(quote_id)})
    if quote:
        comment_text = request.form.get("comment")
        comments_collection.insert_one({"quote_id": quote_id, "text": comment_text, "author": user})

    return redirect(f"/quote/{quote_id}")

@app.route('/delete_comment/<comment_id>', methods=['GET'])
def delete_comment(comment_id):
    session_id = request.cookies.get("session_id", None)
    session_data = session_db.session_collection.find_one({"session_id": session_id})
    if not session_data:
        return redirect("/login")
    
    user = session_data['user']
    comment = comments_collection.find_one({"_id": ObjectId(comment_id)})
    quote = quotes_collection.find_one({"_id": ObjectId(comment['quote_id'])})

    if comment['author'] == user or quote['owner'] == user:
        comments_collection.delete_one({"_id": ObjectId(comment_id)})
    else:
        return redirect("/quotes")

    return redirect("/quotes")

@app.route('/quote/<id>', methods=['GET'])
def get_quote(id):

    all_entries = list(quotes_collection.find({}))
    print(f"All entries: {all_entries}")

    try:
        session_id = request.cookies.get("session_id", None)
        if not session_id:
            return redirect("/login")

        session_data = session_db.session_collection.find_one({"session_id": session_id})
        if not session_data:
            return redirect("/login")

        quote = quotes_collection.find_one({"_id": ObjectId(id)})
        if not quote:
            return "Quote not found", 404

        # make the flask digestible by vue
        quote['_id'] = str(quote['_id'])
        comments = list(comments_collection.find({"quote_id": str(quote['_id'])}))
        for comment in comments:
            comment['_id'] = str(comment['_id'])

        return render_template('view_post.html', quote=quote, comments=comments, user=session_data['user'])
    except InvalidId:
        return "Invalid quote ID", 400
    except Exception as e:
        return f"Internal Server Error: {e}", 500
    
@app.route('/edit_comment/<comment_id>', methods=['GET', 'POST'])
def edit_comment(comment_id):
    session_id = request.cookies.get("session_id", None)
    if not session_id:
        return redirect("/login")

    session_data = session_db.session_collection.find_one({"session_id": session_id})
    if not session_data:
        return redirect("/login")

    user = session_data['user']

    if request.method == 'POST':
        new_text = request.form['text'].strip()
        comment = comments_collection.find_one({"_id": ObjectId(comment_id), "author": user})
        if not comment:
            return "Comment not found", 404

        comments_collection.update_one({"_id": ObjectId(comment_id)}, {"$set": {"text": new_text}})
        return redirect(f'/quote/{comment["quote_id"]}')

    else:
        comment = comments_collection.find_one({"_id": ObjectId(comment_id)})
        if not comment:
            return "Comment not found", 404

        if comment['author'] == user:
            return render_template('edit_comment.html', comment=comment)
        else:
            return redirect("/quote/<id> ")

@app.route('/comment_delete/<comment_id>', methods=['GET'])
def comment_delete(comment_id):
    session_id = request.cookies.get("session_id", None)
    if not session_id:
        return redirect("/login")

    session_data = session_db.session_collection.find_one({"session_id": session_id})
    if not session_data:
        return redirect("/login")

    user = session_data['user']
    comment = comments_collection.find_one({"_id": ObjectId(comment_id)})

    # check if owner
    quote = quotes_collection.find_one({"_id": ObjectId(comment['quote_id'])})
    if not quote:
        return "Quote not found", 404

    # check if owner
    if comment['author'] == user or quote['owner'] == user:
        comments_collection.delete_one({"_id": ObjectId(comment_id)})
        return redirect(f'/quote/{comment["quote_id"]}')