from flask import Flask, render_template, request, make_response, redirect
from mongita import MongitaClientDisk
from bson import ObjectId
from bson.errors import InvalidId
import logging

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

    search_term = request.args.get('search_term', '').strip()

    if search_term:
        data = list(quotes_collection.find({"$or": [
            {"public": True, "text": {"$regex": search_term, "$options": "i"}},
            {"owner": user, "text": {"$regex": search_term, "$options": "i"}}
        ]}))
        for item in data:
            item["_id"] = str(item["_id"])
        return render_template('quotes.html', data=data, user=user)
    else:
        my_quotes = list(quotes_collection.find({"owner": user}))
        public_quotes = list(quotes_collection.find({"public": True}))
        for quote in my_quotes + public_quotes:
            quote["_id"] = str(quote["_id"])
        return render_template("quotes.html", my_quotes=my_quotes, public_quotes=public_quotes, user=user)


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


@app.route("/add", methods=["POST"])
def post_add():
    session_id = request.cookies.get("session_id", None)
    if not session_id:
        response = redirect("/login")
        return response
    # open the session collection
    session_collection = session_db.session_collection
    # get the data for this session
    session_data = list(session_collection.find({"session_id": session_id}))
    if len(session_data) == 0:
        response = redirect("/logout")
        return response
    assert len(session_data) == 1
    session_data = session_data[0]
    # get some information from the session
    user = session_data.get("user", "unknown user")
    text = request.form.get("text", "")
    author = request.form.get("author", "")
    public = request.form.get("public", "") == "on"
    disable_comments = request.form.get("disable_comments") == "on"
    if text != "" and author != "":
        # open the quotes collection
        quotes_collection = quotes_db.quotes_collection
        # insert the quote
        quote_data = {"owner": user, "text": text, "author": author, "public":public, "disable_comments":disable_comments}
        print(quote_data)
        quotes_collection.insert_one(quote_data)
    # usually do a redirect('....')
    return redirect("/quotes")


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
    text = request.form.get("text", "")
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
            # User is not the owner, redirect or show an error
            return redirect("/quotes")  # Redirecting for simplicity
    return redirect("/quotes")    

@app.route('/search')
def search():
    search_term = request.args.get('search_term', '').strip()
    if not search_term:
        return redirect("/quotes")
    
    session_id = request.cookies.get("session_id", None)
    session_collection = session_db.session_collection
    session_data = session_collection.find_one({"session_id": session_id})

    if session_data is None:
        return redirect("/login")

    user = session_data['user']
    quotes_collection = quotes_db.quotes_collection

    data = list(quotes_collection.find({"$or": [
        {"public": True, "text": {"$regex": search_term, "$options": "i"}},
        {"owner": user, "text": {"$regex": search_term, "$options": "i"}}
    ]}))

    print(f"Search term: {search_term}")  # Debugging output
    print(f"Found {len(data)} items")  # Debugging output

    for item in data:
        item["_id"] = str(item["_id"])

    return render_template('quotes.html', data=data, user=user)

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
        new_text = request.form['text']
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

    # Fetch the quote to check if the user is the quote owner
    quote = quotes_collection.find_one({"_id": ObjectId(comment['quote_id'])})
    if not quote:
        return "Quote not found", 404

    # Check if the current user is the comment author or the quote owner
    if comment['author'] == user or quote['owner'] == user:
        comments_collection.delete_one({"_id": ObjectId(comment_id)})
        return redirect(f'/quote/{comment["quote_id"]}')