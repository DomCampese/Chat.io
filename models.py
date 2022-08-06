
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()

''' 
    --- Data Model Summary ---
    Models:
    * User (user_id, username, pwd_hash, messages, current_chatroom, owned_chatrooms)
    * Message (message_id, text, creation_date_time, user, chatroom)
    * Chatroom (chatroom_id, name, messages, owner, users_in_chatroom)

    Relationships:
    * Many-to-one: User has many messages, message has one user
    * Many-to-one: Room has many messages, message has one room
    * Many-to-one: Room has many users, users in one room at a time
    * Many-to-one: Users own many chat room, chat room has one owner
 '''

# (user_id, username, pwd_hash, messages, current_chatroom, owned_chatrooms)
class User(db.Model):
    __tablename__ = 'user'
    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(24), nullable=False)
    pwd_hash = db.Column(db.String(64), nullable=False)
    messages = db.relationship(
        'Message', 
         backref='user', 
         lazy='dynamic', 
         foreign_keys='Message.user_id', 
         post_update=True
    )
    owned_chatrooms = db.relationship(
        'Chatroom', 
        backref='owner', 
        lazy='dynamic', 
        foreign_keys='Chatroom.owner_id', 
        post_update=True
    )
    current_chatroom_id = db.Column(db.Integer, db.ForeignKey('chatroom.chatroom_id', use_alter=True))
    
    def __init__(self, username, pwd_hash):
        self.username = username
        self.pwd_hash = pwd_hash
        self.messages = []
        self.owned_chatrooms = []

    def __repr__(self):
        return f'<User | id: {self.user_id}, username: {self.username}, messages: {[m.message_id for m in self.messages]}, current_chatroom: {self.current_chatroom}, owned_chatrooms: {[c.chatroom_id for c in self.owned_chatrooms]}>'

# (message_id, text, creation_date_time, user, chatroom)
class Message(db.Model):
    __tablename__ = 'message'
    message_id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(200), nullable=False)
    creation_date_time = db.Column(db.DateTime, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id', use_alter=True))
    chatroom_id = db.Column(db.Integer, db.ForeignKey('chatroom.chatroom_id', use_alter=True))

    def __init__(self, text, creation_date_time):
        self.text = text
        self.creation_date_time = creation_date_time

    def __repr__(self):
        return f'<Message | id: {self.message_id}, text: {self.text}, creation_date_time: {self.creation_date_time}, user_id: {self.user_id}, chatroom: {self.chatroom_id}>'

# (chatroom_id, name, messages, owner, users)
class Chatroom(db.Model):
    __tablename__ = 'chatroom'
    chatroom_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    messages = db.relationship(
        'Message', 
        backref='chatroom', 
        lazy='dynamic', 
        foreign_keys='Message.chatroom_id', 
        post_update=True
    )
    users_in_room = db.relationship(
        'User', 
        backref='current_chatroom', 
        lazy='dynamic', 
        foreign_keys='User.current_chatroom_id', 
        post_update=True
    )
    owner_id = db.Column(db.Integer, db.ForeignKey('user.user_id', use_alter=True))

    def __init__(self, name):
        self.name = name
        self.messages = []
        self.users_in_room = []
    
    def __repr__(self):
        return f'<Chatroom | id: {self.chatroom_id}, name: {self.name}, messages: {[m.message_id for m in self.messages]}, owner: {self.owner.user_id}, users_in_room: {[u.user_id for u in self.users_in_room]}>'
