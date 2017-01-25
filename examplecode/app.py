from flask import Flask, render_template, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import and_
import models
import forms
import datetime

app = Flask(__name__)
app.secret_key = 's3cr3t'
app.config.from_object('config')
db = SQLAlchemy(app, session_options={'autocommit': False})
currentuser = None

@app.route('/', methods=['GET', 'POST'])
def login_user():
    global currentuser
    global isStudent
    form = forms.UserLoginFormFactory.form()
    user = currentuser
    if form.validate_on_submit():
        try:
            isStudent = True
            user = db.session.query(models.Student)\
                            .filter(models.Student.email == form.email.data).first()
            if user:
                isStudent = True
                if user.password == form.password.data:
                    currentuser = user
                    form.errors.pop('database', None)
                    return redirect('/profile')
                else:
                    return render_template('login.html', form=form, user=None, msg="Incorrect password!")
            else:
                user = db.session.query(models.Professor)\
                            .filter(models.Professor.email == form.email.data).first()
                if user:
                    isStudent = False
                    if user.password == form.password.data:
                        currentuser = user
                        form.errors.pop('database', None)
                        return redirect('/profile')
                    else:
                        return render_template('login.html', form=form, user=None, msg="Incorrect password!")
                else:
                    return render_template('login.html', form=form, user=None, msg="No user with that email")
        except BaseException as e:
            form.errors['database'] = str(e)
            return render_template('login.html', form=form, user=currentuser)
    else:
        return render_template('login.html', form=form, user=currentuser)

@app.route('/<sectionid>/new-group', methods=['GET', 'POST'])
def new_group(sectionid):
    global currentuser
    if not currentuser:
        return redirect('/')
    
    assignments = db.session.query(models.ProjectAssignment)\
                      .join(models.AssignedTo)\
                      .filter(models.AssignedTo.section_id == sectionid)
    form = forms.GroupNewFormFactory.form(assignments)
    if form.validate_on_submit():
        try:
            form.errors.pop('database', None)
            models.Groups.addNew(form.name.data, sectionid, form.assign.data, currentuser)
            return redirect('/profile')
        except BaseException as e:
            form.errors['database'] = str(e)
            return render_template('new-group.html', form=form, sectionid=sectionid)
    else:
        return render_template('new-group.html', form=form, sectionid=sectionid)

@app.route('/profile')
def user():
    global currentuser
    global isStudent
    if(currentuser):
        currentuser = db.session.query(models.Users)\
            .filter(models.Users.u_id == currentuser.u_id).first()
        if isStudent:
            currentuser = db.session.query(models.Student)\
                .filter(models.Student.u_id == currentuser.u_id).first()
        groups = db.session.query(models.Groups).\
                 join(models.MemberOf).\
                 filter(models.MemberOf.u_id == currentuser.u_id).all()
        classes = db.session.query(models.Section, models.Course.course_name, models.Course.course_pre, models.Section.section_id, models.Section.course_semester, models.Section.university_name, models.Section.university_location, models.Section.course_code, models.Section.section_number).\
                  join(models.RegisteredWith).\
                  join(models.Course, and_(models.Section.course_code==models.Course.course_code, models.Section.course_semester==models.Course.course_semester, models.Section.university_name==models.Course.university_name, models.Section.university_location==models.Course.university_location)).\
                  filter(models.RegisteredWith.u_id == currentuser.u_id).all()
        assignments = db.session.query(models.ProjectAssignment, models.Section.section_id, models.ProjectAssignment.assignment_id, models.ProjectAssignment.date_due, models.ProjectAssignment.description).\
                join(models.AssignedTo).\
                join(models.Section).\
                join(models.RegisteredWith).\
                filter(models.RegisteredWith.u_id == currentuser.u_id).all()
        return render_template('user.html', user=currentuser, isStudent=isStudent, groups=groups, classes=classes, assignments=assignments)
    else:
        return redirect('/')

@app.route('/create-post/<assignment_id>/<section_id>', methods=['GET', 'POST'])
def createPost(assignment_id, section_id):
    global currentuser
    if not currentuser:
        return redirect('/')
    section = db.session.query(models.Section)\
                .filter(models.Section.section_id == section_id).one()
    form = forms.PostNewFormFactory.form()
    if form.validate_on_submit():
        try:
            form.errors.pop('database', None)
            time = str(datetime.datetime.now())
            models.Post.addNew(assignment_id, section.section_id, currentuser.u_id, form.looking_for.data, form.message.data,time)
            return redirect(url_for('getAllPosts', section_id=section.section_id, assignment_id = assignment_id))
        except BaseException as e:
            form.errors['database'] = str(e)
            return render_template('new-post.html', form=form, assignment_id=assignment_id, section_id=section_id)
    else:
        return render_template('new-post.html', form=form, assignment_id=assignment_id, section_id=section_id)

@app.route('/delete-post/<section_id>/<assignment_id>/<post_id>', methods=['GET', 'POST'])
def deletePost(section_id, assignment_id, post_id):
    try: 
        models.Post.deletePost(post_id, currentuser.u_id)
        return redirect(url_for('getAllPosts', section_id=section_id, assignment_id = assignment_id))
    except BaseException as e: 
        return redirect(url_for('getAllPosts', section_id=section_id, assignment_id = assignment_id))

@app.route('/register-class', methods=['GET', 'POST'])
def register_class():
    global currentuser
    if not currentuser:
        return redirect('/')

    form = forms.ClassRegisterFormFactory.form()
    if form.validate_on_submit():
        try:
            form.errors.pop('database', None)
            section = db.session.query(models.Section)\
                      .filter(models.Section.section_id == form.section_code.data).first()
            if section:
                models.RegisteredWith.addNew(currentuser.u_id, section.section_id)
                return redirect('/profile')
            else:
                return render_template('register-class.html', form=form, msg="No class found with that code!")
        except BaseException as e:
            form.errors['database'] = str(e)
            return render_template('register-class.html', form=form)
    else:
        return render_template('register-class.html', form=form)

@app.route('/create-class', methods=['GET', 'POST'])
def create_class():
    global currentuser
    if not currentuser:
        return redirect('/')
    
    universities = db.session.query(models.University).all()
    form = forms.ClassCreateFormFactory.form(universities)
    if form.validate_on_submit():
        try:
            form.errors.pop('database', None)
            university = db.session.query(models.University)\
                .filter(models.University.university_name == form.university.data).first()
            if university:
                models.Course.addNew(form.course_code.data,form.course_semester.data,university.university_name,university.university_location,form.course_name.data,form.course_pre.data)
                startSect = db.session.query(models.Section).count()+1
                for x in xrange(1,form.num_sect.data+1):
                    models.Section.addNew(form.course_code.data,form.course_semester.data,university.university_name,university.university_location,x)
                endSect = db.session.query(models.Section).count()
                for s in xrange(startSect,endSect+1):
                    models.RegisteredWith.addNew(currentuser.u_id, s)
                return redirect('/profile')
            else:
                return render_template('create-class.html', form=form)
        except BaseException as e:
            form.errors['database'] = str(e)
            return render_template('create-class.html', form=form)
    else:
        return render_template('create-class.html', form=form)

@app.route('/create-university', methods=['GET', 'POST'])
def create_university():
    global currentuser
    if not currentuser:
        return redirect('/')
    
    form = forms.UniversityCreateFormFactory.form()
    if form.validate_on_submit():
        try:
            form.errors.pop('database', None)
            models.University.addNew(form.u_name.data,form.u_loc.data)
            return redirect('/create-class')
        except BaseException as e:
            form.errors['database'] = str(e)
            return render_template('create-university.html', form=form)
    else:
        return render_template('create-university.html', form=form)

@app.route('/register-user/', methods=['GET', 'POST'])
def register_user():
    global currentuser
    global isStudent
    form = forms.UserRegisterFormFactory.form()
    if form.validate_on_submit():
        try:
            form.errors.pop('database', None)
            if form.user_type.data == 'pro':
                isStudent = False
            else:
                isStudent = True
            email_check = db.session.query(models.Users)\
                          .filter(models.Users.email == form.email.data).first()
            if(email_check):
                return render_template('register.html', form=form, msg="User with that email already exists")
            else:
                models.Users.addNew(form.name.data, form.phone.data, form.email.data, form.user_type.data, form.password.data)
                currentuser = db.session.query(models.Users).filter(models.Users.email == form.email.data).first()
                return redirect('/profile')
        except BaseException as e:
            form.errors['database'] = str(e)
            return render_template('register.html', form=form)
    else:
        return render_template('register.html', form=form)

@app.route('/feed/<id>')
def classfeed(id):
    section = db.session.query(models.Section)\
        .filter(models.Section.section_id == id).one()
    course = db.session.query(models.Course)\
                    .filter(models.Course.course_code == section.course_code).one()
    assignments = db.session.query(models.ProjectAssignment)\
                    .join(models.AssignedTo)\
                    .join(models.Section)\
                    .filter(models.Section.section_id == id).all()
    return render_template('classfeed.html', section = section, course = course, assignments = assignments)

@app.route('/posts/<section_id>', methods=['GET', 'POST'])
def getPosts(section_id): 
    section = db.session.query(models.Section)\
                .filter(models.Section.section_id==section_id).one()
    course = db.session.query(models.Course)\
                .filter(models.Course.course_code == section.course_code).one()
    assignment_id = request.form.get('selected_assignment')    
    assignment = db.session.query(models.ProjectAssignment)\
                .filter(models.ProjectAssignment.assignment_id == assignment_id).one()
    posts = db.session.query(models.Post)\
            .filter(models.Post.section_id==section.section_id, models.Post.assignment_id==assignment_id)
    return render_template('classfeed-posts.html', posts=posts, assignment=assignment, course=course, section=section, currentuser=currentuser)

@app.route('/posts/<section_id>/<assignment_id>/all', methods=['GET', 'POST'])
def getAllPosts(section_id, assignment_id): 
    section = db.session.query(models.Section)\
                .filter(models.Section.section_id==section_id).one()   
    course = db.session.query(models.Course)\
                .filter(models.Course.course_code == section.course_code).one()
    assignment = db.session.query(models.ProjectAssignment)\
                .filter(models.ProjectAssignment.assignment_id == assignment_id).one()
    posts = db.session.query(models.Post)\
            .filter(models.Post.section_id==section.section_id, models.Post.assignment_id==assignment_id)
    return render_template('classfeed-posts.html', posts=posts, assignment=assignment, course=course, section=section, currentuser=currentuser)

@app.route('/posts/<section_id>/<assignment_id>/need_member', methods=['GET', 'POST'])
def getNeedMemberPosts(section_id, assignment_id): 
    section = db.session.query(models.Section)\
                .filter(models.Section.section_id==section_id).one()   
    course = db.session.query(models.Course)\
                .filter(models.Course.course_code == section.course_code).one()
    assignment = db.session.query(models.ProjectAssignment)\
                .filter(models.ProjectAssignment.assignment_id == assignment_id).one()
    posts = db.session.query(models.Post)\
            .filter(models.Post.section_id==section.section_id, models.Post.assignment_id==assignment_id, models.Post.post_type=="need_member")
    return render_template('classfeed-posts.html', posts=posts, assignment=assignment, course=course, section=section, currentuser=currentuser)

@app.route('/posts/<section_id>/<assignment_id>/need_team', methods=['GET', 'POST'])
def getNeedTeamPosts(section_id, assignment_id): 
    section = db.session.query(models.Section)\
                .filter(models.Section.section_id==section_id).one()   
    course = db.session.query(models.Course)\
                .filter(models.Course.course_code == section.course_code).one()
    assignment = db.session.query(models.ProjectAssignment)\
                .filter(models.ProjectAssignment.assignment_id == assignment_id).one()
    posts = db.session.query(models.Post)\
            .filter(models.Post.section_id==section.section_id, models.Post.assignment_id==assignment_id, models.Post.post_type=="need_team")
    return render_template('classfeed-posts.html', posts=posts, assignment=assignment, course=course, section=section, currentuser=currentuser)

@app.route('/new-assignment', methods=['GET', 'POST'])
def new_assignment():
    global currentuser
    if not currentuser:
        return redirect('/')

    sections = db.session.query(models.Section)\
            .join(models.RegisteredWith)\
            .filter(models.RegisteredWith.u_id == currentuser.u_id)
    form = forms.AssignmentNewFormFactory.form(sections)
    if form.validate_on_submit():
        try:
            form.errors.pop('database', None)
            models.ProjectAssignment.addNew(form.get_sections(),form.date_assigned.data,form.date_due.data,form.description.data)
            return redirect('/profile')
        except BaseException as e:
            form.errors['database'] = str(e)
            return render_template('new-assignment.html', form=form)
    else:
        return render_template('new-assignment.html', form=form)

@app.route('/edit-profile', methods=['GET', 'POST'])
def edit_prof():
    global currentuser
    global isStudent
    global user_info
    if not currentuser:
        return redirect('/')

    if isStudent:
        user_info = db.session.query(models.Student)\
            .filter(models.Student.u_id == currentuser.u_id).first()
    else:
        user_info = db.session.query(models.Professor)\
            .filter(models.Professor.u_id == currentuser.u_id).first()
    form = forms.EditProfileFormFactory.form(user_info, isStudent)
    if form.validate_on_submit():
        try:
            form.errors.pop('database', None)
            models.Users.editUser(form.name.data,form.phone.data,form.email.data,currentuser.u_id)
            if isStudent:
                if form.grad_year.data == '':
                    form.grad_year.data = None
                if form.first_major.data == '':
                    form.first_major.data = None
                if form.second_major.data == '':
                    form.second_major.data = None
                models.Student.editStudent(form.name.data,form.phone.data,form.email.data,currentuser.u_id,form.first_major.data,form.second_major.data,form.grad_year.data)
            else:
                models.Professor.editProf(form.name.data,form.phone.data,form.email.data,currentuser.u_id)
            return redirect('/profile')
        except BaseException as e:
            form.errors['database'] = str(e)
            if isStudent:
                return render_template('edit-profile-student.html', form=form)
            else:
                return render_template('edit-profile.html', form=form)
    else:
        if isStudent:
            return render_template('edit-profile-student.html', form=form)
        else:
            return render_template('edit-profile.html', form=form)

@app.route('/respond/<id>', methods=['GET', 'POST'])
def respond_post(id):
    global currentuser
    #check for if person is logged in
    if not currentuser:
        return redirect('/')
    post = db.session.query(models.Post)\
              .filter(models.Post.post_id == id).first()
    isRegistered = db.session.query(models.RegisteredWith)\
                   .filter(models.RegisteredWith.section_id == post.section_id and models.RegisteredWith.u_id == currentuser.u_id)
    # if not in class, redirect to profile
    if not isRegistered:
        return redirect('/profile')
    else:
        assignment = db.session.query(models.ProjectAssignment)\
                     .filter(models.ProjectAssignment.assignment_id == post.assignment_id).first()
        # if user in group, find it
        group_from = db.session.query(models.Groups)\
                .join(models.MemberOf)\
                .filter(models.MemberOf.u_id == currentuser.u_id)\
                .join(models.WorkingOn)\
                .filter(models.WorkingOn.assignment_id == post.assignment_id).first()
        user_to = db.session.query(models.Users)\
                    .filter(models.Users.u_id == post.u_id).first()
        group_to = None
        if post.post_type == 'need_member':
            group_to = db.session.query(models.Groups)\
                       .join(models.MemberOf)\
                       .filter(models.MemberOf.u_id == user_to.u_id)\
                       .join(models.WorkingOn)\
                       .filter(models.WorkingOn.assignment_id == post.assignment_id).first()

        form = forms.ResponseFormFactory().form();
        if form.validate_on_submit():
            try:
                form.errors.pop('database', None)
                if group_from:
                    models.GroupResponse.addNew(post.post_id, group_from.g_id, post.section_id, form.message.data)
                else:
                    models.UserResponse.addNew(post.post_id, currentuser.u_id, post.section_id, form.message.data)
                return redirect(url_for('getAllPosts', section_id=post.section_id, assignment_id=post.assignment_id))
            except BaseException as e:
                form.errors['database'] = str(e)
                return render_template('response.html', form=form, user_from=currentuser.name, user_to=user_to.name, group_from=group_from, group_to=group_to, id=id, assignment=assignment)
        else:
            return render_template('response.html', form=form, user_from=currentuser.name, user_to=user_to.name, group_from=group_from, group_to=group_to, id=id, assignment=assignment)

@app.route('/membersof/<g_id>')
def membersOf(g_id):
    member = db.session.query(models.Student)\
        .join(models.MemberOf, (models.Student.u_id == models.MemberOf.u_id))\
            .filter(models.MemberOf.g_id == g_id).all()
    group = db.session.query(models.Groups)\
            .filter(models.Groups.g_id == g_id).first()
    group_type = db.session.query(models.ProjectAssignment)\
                 .join(models.WorkingOn)\
                 .filter(models.WorkingOn.g_id == group.g_id).first()
    assign = "Study Group"
    if(group_type):
        assign = group_type.description
    return render_template('membersof.html', member=member, group=group, assign=assign, id=g_id)

@app.route('/<id>/inbox', methods=['GET', 'POST'])
def group_inbox(id):
    # find members of group and all posts made by them
    # figure out the assignment and if user is in group with that assignment
    # find all user/group responses with that id
    assignment = db.session.query(models.WorkingOn)\
                 .filter(models.WorkingOn.g_id == id).first()

    user_responses = db.session.query(models.UserResponse, models.UserResponse.message, models.Users.name, models.UserResponse.time_posted, models.UserResponse.u_id, models.Post.post_id)\
                     .join(models.Post)\
                     .filter(models.Post.assignment_id == assignment.assignment_id and models.Post.post_type == 'need_member')\
                     .join(models.Users, models.Users.u_id == models.UserResponse.u_id)\
                     .join(models.MemberOf, models.MemberOf.u_id == models.Post.u_id and models.MemberOf.g_id == id).all()

    if request.method == 'POST':
        for u_r in user_responses:
            key = str(u_r.post_id)+" "+str(u_r.u_id)
            if request.form[key] == 'Accept':
                models.MemberOf.addNew(u_r.u_id, id)
                models.UserResponse.remove(u_r.post_id, u_r.u_id)
                return redirect(url_for('membersOf', g_id=id))
            elif request.form[key] == 'Reject':
                models.UserResponse.remove(u_r.post_id, u_r.u_id)
                return redirect(url_for('group_inbox', id=id))
    return render_template('group-inbox.html', user_responses=user_responses, id=id)

@app.route('/my_inbox', methods=['GET', 'POST'])
def inbox():
    user_responses = db.session.query(models.UserResponse, models.ProjectAssignment.description, models.Users.name, models.UserResponse.u_id, models.UserResponse.post_id, models.UserResponse.message, models.UserResponse.time_posted, models.Post.assignment_id, models.Post.section_id)\
                     .join(models.Post, models.Post.post_id == models.UserResponse.post_id)\
                     .filter(models.UserResponse.u_id != currentuser.u_id and models.Post.u_id == currentuser.u_id and models.Post.post_type == 'need_team')\
                     .join(models.Users, models.Users.u_id == models.UserResponse.u_id)\
                     .join(models.ProjectAssignment).all()\
 
    group_responses = db.session.query(models.GroupResponse, models.ProjectAssignment.description, models.Groups.group_name, models.GroupResponse.g_id, models.GroupResponse.post_id, models.GroupResponse.message, models.GroupResponse.time_posted)\
                      .join(models.Post)\
                      .join(models.Groups)\
                      .join(models.ProjectAssignment)\
                      .filter(models.Post.post_id == models.GroupResponse.post_id and models.Post.post_type == 'need_team').all()
    if request.method == 'POST':
        for u_r in user_responses:
            key = str(u_r.post_id)+" "+str(u_r.u_id)
            if request.form[key] == 'Accept':
                models.Groups.addNewTwoUsers(request.form["group_name"], u_r.section_id, u_r.assignment_id, currentuser.u_id, u_r.u_id)
                models.UserResponse.remove(u_r.post_id, u_r.u_id)
                return redirect('/profile')
            elif request.form[key] == 'Reject':
                models.UserResponse.remove(u_r.post_id, u_r.u_id)
                return redirect('/my_inbox')
        for g_r in group_responses:
            key = str(g_r.post_id)+" "+str(g_r.g_id)
            if request.form[key] == 'Accept':
                models.MemberOf.addNew(currentuser.u_id, g_r.g_id)
                models.GroupResponse.remove(g_r.post_id, g_r.g_id)
                return redirect(url_for('memberOf', g_id=g_r.g_id))
            elif request.form[key] == 'Reject':
                models.GroupResponse.remove(g_r.post_id, g_r.g_id)
                return redirect('/my_inbox')
    return render_template('user-inbox.html', user_responses=user_responses, group_responses=group_responses)

@app.template_filter('pluralize')
def pluralize(number, singular='', plural='s'):
    return singular if number in (0, 1) else plural

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
