from sqlalchemy import sql, orm, join, func
from sqlalchemy.sql import text 
from app import db
import datetime

class Users(db.Model):
    __tablename__ = 'users'
    u_id = db.Column('u_id', db.Integer(), primary_key=True)
    name = db.Column('name', db.String(256))
    phone = db.Column('phone', db.String(15))
    email = db.Column('email', db.String(256))
    password = db.Column('password', db.String(256))
    @staticmethod
    def addNew(name, phone, email, user_type, password):
        try:
            u_id = db.session.query(Users).count()+1
            db.session.execute('INSERT INTO users VALUES(:u_id, :name, :phone, :email, :password)',
                               dict(u_id=u_id, name=name, phone=phone, email=email, password=password))
            if user_type == 'pro':
                db.session.execute('INSERT INTO professor VALUES(:u_id, :name, :phone, :email, :password)',
                    dict(u_id=u_id, name=name, phone=phone, email=email, password=password))
            else:
                db.session.execute('INSERT INTO student VALUES(:u_id, :name, :phone, :email, :password)',
                    dict(u_id=u_id, name=name, phone=phone, email=email, password=password))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e
    @staticmethod
    def editUser(name, phone, email, u_id):
        try:
            db.session.execute('UPDATE users SET name = :name, phone = :phone, email = :email, u_id = :u_id'
                               ' WHERE u_id = :u_id',
                               dict(u_id=u_id, name=name, phone=phone, email=email))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

class Professor(db.Model):
    __tablename__ = 'professor'
    u_id = db.Column('u_id', db.Integer(), db.ForeignKey('Users.u_id'), primary_key=True)
    name = db.Column('name', db.String(256))
    phone = db.Column('phone', db.Integer())
    email = db.Column('email', db.String(256))
    password = db.Column('password', db.String(256))
    @staticmethod
    def editProf(name, phone, email, u_id):
        try:
            db.session.execute('UPDATE professor SET name = :name, phone = :phone, email = :email, u_id = :u_id'
                               ' WHERE u_id = :u_id',
                               dict(u_id=u_id, name=name, phone=phone, email=email))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

class Student(db.Model):
    __tablename__ = 'student'
    u_id = db.Column('u_id', db.Integer(), db.ForeignKey('Users.u_id'), primary_key=True)
    name = db.Column('name', db.String(256))
    phone = db.Column('phone', db.Integer())
    email = db.Column('email', db.String(256))
    password = db.Column('password', db.String(256))
    first_major = db.Column('first_major', db.String(256))
    second_major = db.Column('second_major', db.String(256))
    grad_year = db.Column('grad_year', db.Integer())
    @staticmethod
    def editStudent(name, phone, email, u_id, first_major, second_major, grad_year):
        try:
            db.session.execute('UPDATE student SET name = :name, phone = :phone, email = :email, first_major = :first_major, second_major = :second_major, grad_year = :grad_year, u_id = :u_id'
                ' WHERE u_id = :u_id',
                dict(u_id=u_id, name=name, phone=phone, email=email, first_major=first_major, second_major=second_major, grad_year=grad_year))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

class Groups(db.Model):
    __tablename__ = 'groups'
    group_name = db.Column('group_name', db.String(256))
    g_id = db.Column('g_id', db.Integer(), primary_key=True)
    @staticmethod
    def addNew(group_name, section_id, assignment_id, currentuser):
        try:
            g_id = db.session.query(Groups).count()+1
            section_id = int(section_id)
            db.session.execute('INSERT INTO groups VALUES(:group_name, :g_id)',
                               dict(group_name=group_name, g_id=g_id))
            if assignment_id == "none":
                db.session.execute('INSERT INTO studygroup VALUES(:g_id, :name)',
                               dict(g_id=g_id, name=group_name))
                db.session.execute('INSERT INTO studyingfor VALUES(:g_id, :section_id)',
                               dict(g_id=g_id, section_id=section_id))
            else:
                db.session.execute('INSERT INTO projectgroup VALUES(:g_id, :name)',
                                   dict(g_id=g_id, name=group_name))
                db.session.execute('INSERT INTO workingon VALUES(:g_id, :assignment_id)',
                                   dict(g_id=g_id, assignment_id=int(assignment_id)))
            db.session.execute('INSERT INTO memberof VALUES(:u_id, :g_id, :is_leader)',
                dict(u_id=currentuser.u_id, g_id=g_id, is_leader='yes'))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e
    @staticmethod
    def addNewTwoUsers(group_name, section_id, assignment_id, user1, user2):
        try:
            g_id = db.session.query(Groups).count()+1
            section_id = int(section_id)
            db.session.execute('INSERT INTO groups VALUES(:group_name, :g_id)',
                               dict(group_name=group_name, g_id=g_id))
            db.session.execute('INSERT INTO projectgroup VALUES(:g_id, :name)',
                                   dict(g_id=g_id, name=group_name))
            db.session.execute('INSERT INTO workingon VALUES(:g_id, :assignment_id)',
                                   dict(g_id=g_id, assignment_id=int(assignment_id)))
            db.session.execute('INSERT INTO memberof VALUES(:u_id, :g_id, :is_leader)',
                dict(u_id=user1, g_id=g_id, is_leader='yes'))
            db.session.execute('INSERT INTO memberof VALUES(:u_id, :g_id, :is_leader)',
                dict(u_id=user2, g_id=g_id, is_leader='no'))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

class MemberOf(db.Model):
    __tablename__ = 'memberof'
    u_id = db.Column('u_id', db.Integer(), db.ForeignKey('users.u_id'), primary_key=True)
    g_id = db.Column('g_id', db.Integer(), db.ForeignKey('groups.g_id'), primary_key=True)
    is_leader = db.Column('is_leader', db.String(3))
    @staticmethod
    def addNew(u_id, g_id):
        try:
            db.session.execute('INSERT INTO memberof VALUES(:u_id, :g_id, :is_leader)',
                               dict(u_id=u_id, g_id=g_id, is_leader='no'))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

class University(db.Model):
    __tablename__ = 'university'
    university_name = db.Column('university_name', db.String(256), primary_key=True)
    university_location = db.Column('university_location', db.String(256), primary_key=True)
    @staticmethod
    def addNew(university_name, university_location):
        try:
            db.session.execute('INSERT INTO university VALUES(:university_name, :university_location)',
                           dict(university_name=university_name, university_location=university_location))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

class Post(db.Model):
    __tablename__ = 'post'
    post_id = db.Column('post_id', db.Integer(), primary_key=True)
    assignment_id = db.Column('assignment_id', db.Integer(), db.ForeignKey('projectassignment.assignment_id'), primary_key=True) 
    section_id = db.Column('section_id', db.Integer(), db.ForeignKey('section.section_id'), primary_key=True) 
    u_id = db.Column('u_id', db.Integer(), db.ForeignKey('users.u_id'))
    post_type = db.Column('post_type', db.String(100))
    message = db.Column('message', db.String(1000))
    time_posted = db.Column('time_posted', db.String())
    @staticmethod
    def addNew(assignment_id, section_id, u_id, looking_for, message, time_posted):
        try:
            #post_id = db.session.query(Post).count()+1
            max_post_id = db.session.query(db.func.max(Post.post_id)).scalar()
            post_id = int(max_post_id) + 1
            section_id = int(section_id)
            db.session.execute('INSERT INTO post VALUES(:post_id, :assignment_id, :section_id, :u_id, :post_type, :message, :time_posted)',
                               dict(post_id = post_id, assignment_id=assignment_id, section_id=section_id,u_id=u_id,post_type=looking_for,message=message,time_posted=time_posted))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e
    @staticmethod
    def deletePost(post_id, u_id):
        post = db.session.query(Post)\
                .filter(Post.post_id == post_id).one()
        if (post.post_type == 'need_team'):
            try: 
                UserResponse.remove(post_id, u_id)
            except Exception as e:
                GroupResponse.remove(post_id, u_id)
        elif (post.post_type == 'need_member'):
            UserResponse.remove(post_id, u_id)
        try: 
            db.session.execute('DELETE FROM post WHERE post_id = :post_id', 
                                dict(post_id = post_id))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e


class ProjectAssignment(db.Model):
    __tablename__ = 'projectassignment'
    assignment_id = db.Column('assignment_id', db.Integer(), primary_key=True)
    date_assigned = db.Column('date_assigned', db.String(20))
    date_due = db.Column('date_due', db.String(20))
    description = db.Column('description', db.String(1000))
    posts = orm.relationship('Post')
    @staticmethod
    def addNew(sections, assigned, due, desc):
        try:
            a_id = db.session.query(ProjectAssignment).count()+1
            db.session.execute('INSERT INTO projectassignment VALUES(:assignment_id, :date_assigned, :date_due, :description)',
                           dict(assignment_id=a_id, date_assigned=assigned, date_due=due, description=desc))
            for section in sections:
                db.session.execute('INSERT INTO assignedto VALUES(:assignment_id, :section_id)',
                    dict(assignment_id=a_id, section_id=int(section)))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

class AssignedTo(db.Model):
    __tablename__ = 'assignedto'
    assignment_id = db.Column('assignment_id', db.String(256), db.ForeignKey('projectassignment.assignment_id'), primary_key=True)
    section_id = db.Column('section_id', db.Integer(), db.ForeignKey('section.section_id'), primary_key=True)      

class Course(db.Model):
    __tablename__ = 'course'
    course_code = db.Column('course_code', db.String(256), primary_key=True)
    course_semester = db.Column('course_semester', db.String(10), primary_key=True)
    university_name = db.Column('university_name', db.String(256), db.ForeignKey('university.university_name'), primary_key=True)
    university_location = db.Column('university_location', db.String(256), db.ForeignKey('university.university_location'), primary_key=True)
    course_name = db.Column('course_name', db.String(256))
    course_pre = db.Column('course_pre', db.String(256))
    @staticmethod
    def addNew(course_code, course_semester, university_name, university_location, course_name, course_pre):
        try:
            db.session.execute('INSERT INTO course VALUES(:course_code, :course_semester, :university_name, :university_location, :course_name, :course_pre)',
            dict(course_code=course_code, course_semester=course_semester, university_name=university_name, university_location=university_location, course_name=course_name, course_pre=course_pre))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

class Section(db.Model):
    __tablename__ = 'section'
    section_id = db.Column('section_id', db.Integer(), primary_key=True)
    section_number = db.Column('section_number', db.Integer())
    course_code = db.Column('course_code', db.String(256), db.ForeignKey('course.course_code'), primary_key=True)
    course_semester = db.Column('course_semester', db.String(256), db.ForeignKey('course.course_semester'), primary_key=True)
    university_name = db.Column('university_name', db.String(256), db.ForeignKey('university.university_name'), primary_key=True)
    university_location = db.Column('university_location', db.String(256), db.ForeignKey('university.university_location'), primary_key=True)
    @staticmethod
    def addNew(course_code, course_semester, university_name, university_location, section_number):
            try:
                section_id = db.session.query(Section).count()+1
                section_number = int(section_number)
                db.session.execute('INSERT INTO section VALUES(:section_id, :section_number, :course_code, :course_semester, :university_name, :university_location)',
                    dict(section_id=section_id, section_number=section_number, course_code=course_code, course_semester=course_semester, university_name=university_name, university_location=university_location))
                db.session.commit()
            except Exception as e:
                   db.session.rollback()
                   raise e

class RegisteredWith(db.Model):
    __tablename__ = 'registeredwith'
    u_id = db.Column('u_id', db.Integer(), db.ForeignKey('users.u_id'), primary_key=True)
    section_id = db.Column('section_id', db.Integer(), db.ForeignKey('section.section_id'), primary_key=True)
    @staticmethod
    def addNew(u_id, section_id):
        try:
            db.session.execute('INSERT INTO registeredwith VALUES(:u_id, :section_id)',
                               dict(u_id=u_id, section_id=section_id))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

class Add(db.Model):
    __tablename__ = 'join'
    j_id = db.Column('j_id', db.Integer(), primary_key=True)
    g_id = db.Column('g_id', db.Integer(), db.ForeignKey('groups.g_id'))
    message = db.Column('message', db.String(1000))
    approved = db.Column('approved', db.String(1))
    sent_to = db.Column('sent_to', db.Integer(), db.ForeignKey('users.u_id'))
    sent_by = db.Column('sent_by', db.Integer(), db.ForeignKey('users.u_id'))

class SentTo(db.Model):
    __tablename__ = 'sentto'
    j_id = db.Column('j_id', db.Integer(), db.ForeignKey('join.j_id'), primary_key=True)    
    u_id = db.Column('u_id', db.Integer(), db.ForeignKey('Users.u_id'), primary_key=True)  

class SentBy(db.Model):
    __tablename__ = 'sentby'
    j_id = db.Column('j_id', db.Integer(), db.ForeignKey('join.j_id'), primary_key=True)    
    u_id = db.Column('u_id', db.Integer(), db.ForeignKey('Users.u_id'), primary_key=True)     

class ProjectGroup(db.Model):
    __tablename__ = 'projectgroup'
    g_id = db.Column('g_id', db.Integer(), db.ForeignKey('groups.g_id'), primary_key=True)  
    name = db.Column('name', db.String(256))

class StudyGroup(db.Model):
    __tablename__ = 'studygroup'
    g_id = db.Column('g_id', db.Integer(), db.ForeignKey('groups.g_id'), primary_key=True)  
    name = db.Column('name', db.String(256))

class WorkingOn(db.Model):
    __tablename__ = 'workingon'
    g_id = db.Column('g_id', db.Integer(), db.ForeignKey('groups.g_id'), primary_key=True)
    assignment_id = db.Column('assignment_id', db.Integer(), db.ForeignKey('projectassignment.assignment_id'), primary_key=True)         

class StudyingFor(db.Model):
    __tablename__ = 'studyingfor'
    g_id = db.Column('g_id', db.Integer(), db.ForeignKey('groups.g_id'), primary_key=True)
    section_id = db.Column('section_id', db.Integer(), db.ForeignKey('section.section_id'), primary_key=True)

class GroupResponse(db.Model):
    __tablename__ = 'groupresponse'
    post_id = db.Column('post_id', db.Integer(), db.ForeignKey('post.post_id'), primary_key=True)
    g_id = db.Column('g_id', db.Integer(), db.ForeignKey('groups.g_id'), primary_key=True)
    section_id = db.Column('section_id', db.Integer(), db.ForeignKey('section.section_id'))
    time_posted = db.Column('time_posted', db.String(100))
    message = db.Column('message', db.String(1000))
    approved = db.Column('approved', db.Boolean())
    @staticmethod
    def addNew(post_id, g_id, section_id, message):
        try:
            time = str(datetime.datetime.now())
            db.session.execute('INSERT INTO groupresponse VALUES(:post_id, :g_id, :section_id, :time_posted, :message, :approved)',
                               dict(post_id=post_id, g_id=g_id, section_id=section_id, time_posted=time, message=message, approved=False))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e
    @staticmethod
    def remove(post_id, g_id):
        try:
            db.session.execute('DELETE FROM groupresponse WHERE post_id = :post_id AND g_id = :g_id',
            dict(post_id=post_id, g_id=g_id))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

class UserResponse(db.Model):
    __tablename__ = 'userresponse'
    post_id = db.Column('post_id', db.Integer(), db.ForeignKey('post.post_id'), primary_key=True)
    u_id = db.Column('u_id', db.Integer(), db.ForeignKey('users.u_id'), primary_key=True)
    section_id = db.Column('section_id', db.Integer(), db.ForeignKey('section.section_id'))
    time_posted = db.Column('time_posted', db.String())
    message = db.Column('message', db.String(1000))
    approved = db.Column('approved', db.Boolean())
    @staticmethod
    def addNew(post_id, u_id, section_id, message):
        try:
            time = str(datetime.datetime.now())
            db.session.execute('INSERT INTO userresponse VALUES(:post_id, :u_id, :section_id, :time_posted, :m\
essage, :approved)',
                               dict(post_id=post_id, u_id=u_id, section_id=section_id, time_posted=time, message=message, approved=False))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e
    @staticmethod
    def remove(post_id, u_id):
        try:
            db.session.execute('DELETE FROM userresponse WHERE post_id = :post_id AND u_id = :u_id',
                               dict(post_id=post_id, u_id=u_id))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e
