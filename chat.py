
import os
import json
import datetime
from datetime import datetime

from flask import Flask, request, session, url_for, redirect, render_template, abort, g, flash, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import and_

from models import db, User, Message, Chatroom

app = Flask(__name__)

app.config.update(dict(
	SECRET_KEY='Sample key for testing purposes only',
	SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(app.root_path, 'chat.db'),
	SQLALCHEMY_TRACK_MODIFICATIONS=True,
))
app.config.from_envvar('CHAT_SETTINGS', silent=True)

db.init_app(app)

@app.cli.command('initdb')
def initdb_command():
	db.create_all()
	print('Database initialized.')

@app.cli.command('cleardb')
def cleardb_command():
	response = ''
	while response.lower() != 'y' and response.lower() != 'n':
		response = input('Are you sure you want to clear the database? This cannot be undone. (y/n): ')
		if response.lower() == 'y':
			db.drop_all()
			print("Database cleared.")
		elif response.lower() == 'n':
			print("Cancelled. Database not cleared.")

@app.before_request
def before_request():
	g.user = None
	if 'user_id' in session:
		g.user = User.query.filter_by(user_id=session['user_id']).first()

@app.route('/')
def root():
	if not g.user:
		return redirect(url_for('login'))
	return redirect(url_for('lobby'))

@app.route('/lobby')
def lobby():
	if not g.user:
		return redirect(url_for('login'))
	# Clear the user's chatroom from db (on return)
	if g.user.current_chatroom:
		g.user.current_chatroom = None
		db.session.commit()
	
	return render_template('lobby.html', chatrooms=Chatroom.query.all())

@app.route('/chatroom/<chatroom_id>')
def chatroom(chatroom_id):
	if not g.user:
		return redirect(url_for('login'))

	chatroom = Chatroom.query.filter_by(chatroom_id=chatroom_id).first()

	# Either the room was deleted or user should not be here
	if not chatroom:
		return redirect(url_for('lobby'))

	# If the user is in a chatroom elsewhere, send them to the lobby
	if g.user.current_chatroom and g.user.current_chatroom != chatroom:
		flash(f"You may only be in one chatroom at a time.")
		return redirect(url_for('lobby'))

	# Add the user to the chatroom
	chatroom.users_in_room.append(g.user)
	db.session.commit()
	# Clear last updated time so user gets all messages upon entering a room (then gets new messages each second)
	session.pop('last_updated', None)
	
	return render_template('chatroom.html', chatroom=chatroom)

@app.route('/create_message/<chatroom_id>', methods=['POST'])
def create_message(chatroom_id):
	if not g.user:
		return redirect(url_for('login'))
	if not g.user.current_chatroom:
		return (jsonify({'body':"User not in this chatroom"}), 401, {'ContentType':'application/json'})
	# Handles empty or phatom message
	
	json = request.get_json()
	if not 'text' in json.keys() or json['text'] == '':
		return (jsonify({'body':"Message must have text"}), 400, {'ContentType':'application/json'})

	chatroom = Chatroom.query.filter_by(chatroom_id=chatroom_id).first()

	message = Message(json['text'], datetime.now())
	chatroom.messages.append(message)
	g.user.messages.append(message)
	db.session.commit()
	return (jsonify({'body':"Message created successfully"}), 200, {'ContentType':'application/json'})

@app.route('/create_chatroom', methods=['GET', 'POST'])
def create_chatroom():
	if not g.user:
		return redirect(url_for('login'))

	error = None
	if request.method == 'POST':
		if not request.form['name']:
			error = 'Please enter a Chat Room name'
		else:
			# Create the chatroom
			chatroom = Chatroom(request.form['name'])
			# Add it to this user's owned chatrooms
			g.user.owned_chatrooms.append(chatroom)
			db.session.commit()
			flash(f'Chat Room {chatroom.name} created successfully')
			return redirect(url_for('lobby'))
	# Get request
	return render_template('create_chatroom.html', error=error)

@app.route('/delete_chatroom/<chatroom_id>', methods=['POST'])
def delete_chatroom(chatroom_id):
	if not g.user:
		return redirect(url_for('login'))

	chatroom = Chatroom.query.filter_by(chatroom_id=chatroom_id).first()

	if not chatroom: # No such chatroom 
		return abort(404)
	if g.user != chatroom.owner:
		# Forbidden, not the owner
		return abort(403)

	# Delete all the messages
	for message in chatroom.messages:
		db.session.delete(message)
	# Delete the chatroom
	db.session.delete(chatroom)
	db.session.commit()
	flash('Chatroom deleted successfully')
	return redirect(url_for('lobby'))		

@app.route('/messages/<chatroom_id>')
def messages(chatroom_id):
	if not g.user:
		abort(401)

	chatroom = Chatroom.query.filter_by(chatroom_id=chatroom_id).first()
	if not chatroom:
		flash('The owner deleted the chatroom')
		abort(401)

	# No longer in the room
	if not g.user.current_chatroom or g.user.current_chatroom.chatroom_id != int(chatroom_id):
		abort(401)

	messages = None
	if 'last_updated' in session.keys():
		last_updated = datetime.fromisoformat(session['last_updated'])
		# Return only new messages
		messages = Message.query.filter(and_((Message.creation_date_time > last_updated), Message.chatroom == chatroom)).order_by(Message.creation_date_time).all()
	else:
		# Return all messages
		messages = Message.query.order_by(Message.creation_date_time).filter(Message.chatroom == chatroom).all()

	# Only send what's necessary
	messages_clean = []
	for m in messages:
		username = m.user.username
		if username == g.user.username:	
			username = 'Me'
		text = m.text
		creation_date_time = m.creation_date_time.strftime('%m/%d/%Y %H:%M')
		messages_clean.append({'text' : text, 'creation_date_time' : creation_date_time, 'username' : username})

	session['last_updated'] = datetime.now().isoformat();
	return jsonify(messages_clean)


@app.route('/login', methods=['GET', 'POST'])
def login():
	if g.user:
		# Sends user to lobby
		return redirect(url_for('root'))
	error = None
	if request.method == 'POST':
		# Need to grab this user's object (g.user is none before they log in)
		user = User.query.filter_by(username=request.form['username']).first()
		if user is None or not check_password_hash(user.pwd_hash, request.form['password']):
			error = 'Invalid username or password'
		else:
			flash(f'({user.username}) logged in successfully')
			session['user_id'] = user.user_id
			return redirect('/')
	# Get request + not logged in
	return render_template('login.html', error=error)

@app.route('/logout')
def logout():
	if not g.user:
		return redirect(url_for('root'))

	flash('Logged out successfully')
	session.pop('user_id', None)
	return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
	if g.user:
		return redirect(url_for('root'))
	
	error = None
	if request.method == 'POST':
		if not request.form['username']:
			error = 'Please enter a username'
		elif not request.form['password']:
			error = 'Please enter a password'
		elif request.form['password'] != request.form['password2']:
			error = 'Passwords do not match'
		elif User.query.filter_by(username=(request.form['username'])).first():
			error = 'Username already taken'
		else:
			db.session.add(User(request.form['username'], generate_password_hash(request.form['password'])))
			db.session.commit()
			flash('Account created successfully')
			return redirect(url_for('login'))
	return render_template('signup.html', error=error)
