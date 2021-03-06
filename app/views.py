'''
NoI Views

All views in the app, as a blueprint
'''

from flask import (Blueprint, render_template, request, flash,
                   redirect, url_for, current_app)
from flask_babel import lazy_gettext, gettext
from flask_login import login_required, current_user

from app.models import db, User, UserLanguage, UserExpertiseDomain
from app.forms import UserForm, SearchForm

from sqlalchemy import func, desc
from sqlalchemy.dialects.postgres import array

from boto.s3.connection import S3Connection

import mimetypes

views = Blueprint('views', __name__)  # pylint: disable=invalid-name


@views.route('/')
def main_page():
    '''
    Main NoI page
    '''
    return render_template('main.html', SKIP_NAV_BAR=False)


@views.route('/about')
def about_page():
    '''
    NoI about page.
    '''
    return render_template('about.html')


#@views.route('/login', methods=['GET', 'POST'])
#def login():
#    print session
#    if request.method == 'GET':
#        return render_template('login-page.html', **{'SKIP_NAV_BAR': False})
#    if request.method == 'POST':
#        social_login = json.loads(request.form.get('social-login'))
#        session['social-login'] = social_login
#        userid = social_login['userid']
#        userProfile = db.getUser(userid)
#        if userProfile:
#            session['user-profile'] = userProfile
#        else:
#            db.createNewUser(userid, social_login['first_name'],
#            social_login['last_name'], social_login['picture'])
#            userProfile = db.getUser(userid)
#            session['user-profile'] = userProfile
#        flash('You are authenticated using your %s Credentials.' % social_login['idp'])
#        g.is_logged_in = True
#        return jsonify({'result': 0})


#@views.route('/logout')
#def logout():
#    idp = session['social-login']['idp']
#    session.clear()
#    return redirect(url_for('main_page', **{'logout': idp}))


#@views.route('/edit/<userid>', methods=['GET', 'POST'])
#def edit_user(userid):
#    if request.method == 'GET':
#        userProfile = db.getUser(userid)  # We get some stuff from the DB.
#        return render_template('my-profile.html',
#                               **{'userProfile': userProfile})
#
#    if current_user.id:
#        if request.method == 'POST' and userid == current_user.id:
#            userProfile = json.loads(request.form.get('me'))
#            session['user-profile'] = userProfile
#            db.updateCoreProfile(userProfile)
#            flash('Your profile has been saved.')
#            return render_template('my-profile.html', **{'userProfile': userProfile})


@views.route('/me', methods=['GET', 'POST'])
@login_required
def my_profile():
    '''
    Show user their profile, let them edit it
    '''
    form = UserForm(obj=current_user)
    if request.method == 'GET':
        return render_template('my-profile.html', form=form)
    elif request.method == 'POST':
        #userProfile = json.loads(request.form.get('me'))
        #session['user-profile'] = userProfile
        #db.updateCoreProfile(userProfile)
        #flash('Your profile has been saved. <br/>You may also want to <a'
        #      'href="/my-expertise">tell us what you know</a>.')
        #session['has_created_profile'] = True
        form.populate_obj(current_user)
        if form.validate():

            if form.picture.has_file():
                conn = S3Connection(current_app.config['S3_ACCESS_KEY_ID'],
                                    current_app.config['S3_SECRET_ACCESS_KEY'])
                bucket = conn.get_bucket(current_app.config['S3_BUCKET_NAME'])
                bucket.make_public(recursive=False)

                mimetype = mimetypes.guess_type(form.picture.data.filename)[0]

                k = bucket.new_key(current_user.picture_path)
                k.set_metadata('Content-Type', mimetype)
                k.set_contents_from_file(form.picture.data)
                k.make_public()

                current_user.has_picture = True

            db.session.add(current_user)
            db.session.commit()
            flash(lazy_gettext('Your profile has been saved. <br/>You may also want to <a '
                               'href="/my-expertise">tell us what you know</a>.'))
        else:
            flash(lazy_gettext(u'Could not save, please correct errors below: {}'.format(
                form.errors)))

        return render_template('my-profile.html', form=form)


@views.route('/my-expertise', methods=['GET', 'POST'])
@login_required
def my_expertise():
    '''
    Allow user to edit their expertise
    '''
    #if 'social-login' not in session:
    #    flash('You need to be authenticated in order to fill your expertise.', 'error')
    #    return redirect(url_for('login'))
    #social_login = session['social-login']
    #userid = social_login['userid']
    if request.method == 'GET':
        return render_template('my-expertise.html')
    elif request.method == 'POST':
        for k, val in request.form.iteritems():
            current_user.set_skill(k, val)
        db.session.add(current_user)
        db.session.commit()
        flash(lazy_gettext("""Your expertise has been updated.<br/>
        What you can do next:
        <ul>
        <li><a href="/search">Search for innovators</a></li>
        <li>Fill another expertise questionnaire below</li>
        <li>View your <a href="/user/{}">public profile</a></li>
        """).format(current_user.id))
        return render_template('my-expertise.html')


@views.route('/dashboard')
@login_required
def dashboard():
    '''
    Dashboard of what's happening on the platform.
    '''
    top_countries = db.session.query(func.count(User.id)) \
            .group_by(User.country) \
            .order_by(desc(func.count(User.id))).all()
    users = [{'latlng': u.latlng,
              'first_name': u.first_name,
              'last_name': u.last_name} for u in User.query.all()]
    occupations = db.session.query(func.count(User.id)) \
            .group_by(User.organization_type) \
            .order_by(desc(func.count(User.id))).all()

    return render_template('dashboard.html', **{'top_countries': top_countries,
                                                'ALL_USERS': users,
                                                'OCCUPATIONS': occupations})

#@views.route('/dashboard-2')
#def dashboard2():
#    return render_template('dashboard-2.html', **{'top_countries': top_countries})

#@views.route('/vcard/<userid>')
#def vcard(userid):
#    user = db.getUser(userid)
#    if user:
#        card = make_vCard(user['first_name'], user['last_name'], user['org'],
#        user['title'], user['email'], user['city'], user['country'])
#        return Response(card, mimetype='text/vcard')
#    else:
#        flash('This is does not correspond to a valid user.')
#        return redirect(url_for('main_page'))


@views.route('/user/<userid>')
@login_required
def get_user(userid):
    '''
    Public-facing profile view
    '''
    user = User.query.get(userid)
    if user:
        #if 'social-login' in session:
        #    my_userid = session['social-login']['userid']
        #else:
        #    my_userid = 'anonymous'
        #query_info = {'user-agent': request.headers.get('User-Agent'),
        #              'type': '/user', 'userid': my_userid}
        #db.logQuery(my_userid, query_info)
        return render_template('user-profile.html', user=user)
    else:
        flash('This is does not correspond to a valid user.')
        return redirect(url_for('views.search'))


@views.route('/search', methods=['GET', 'POST'])
@login_required
def search():
    '''
    Generic search page
    '''
    form = SearchForm()
    if request.method == 'GET':
        return render_template('search.html', form=form)
    if request.method == 'POST':
        query = User.query  #pylint: disable=no-member

        if form.country.data and form.country.data != 'ZZ':
            query = query.filter(User.country == form.country.data)

        if form.locales.data:
            query = query.join(User.languages).filter(UserLanguage.locale.in_(
                form.locales.data))

        if form.expertise_domain_names.data:
            query = query.join(User.expertise_domains).filter(UserExpertiseDomain.name.in_(
                form.expertise_domain_names.data))

        if form.fulltext.data:
            query = query.filter(func.to_tsvector(func.array_to_string(array([
                User.first_name, User.last_name, User.organization, User.position,
                User.projects]), ' ')).op('@@')(func.plainto_tsquery(form.fulltext.data)))

        # TODO ordering by relevance
        return render_template('search-results.html',
                               title='Expertise search',
                               form=form,
                               results=query.limit(20).all())


@views.route('/match')
@login_required
def match():
    '''
    Find innovators with answers
    '''
    if not current_user.skill_levels:
        flash(gettext('Before we can match you with fellow innovators, you need to '
                      'enter your expertise below first.'), 'error')
        return redirect(url_for('views.my_expertise'))
    return render_template('search-results.html',
                           title='People Who Know what I do not',
                           results=current_user.helpful_users)


# @views.route('/match-knn')
# @login_required
# def knn():
#     '''
#     Find nearest neighbor (innovators most like you)
#     '''
#     if not current_user.skill_levels:
#         flash('Before we can find innovators like you, you need to '
#               '<a href="/my-expertise">fill your expertise</a> first.', 'error')
#         return redirect(url_for('views.my_expertise'))
#     experts = current_user.nearest_neighbors
#     return render_template('search-results.html', title='People most like me',
#                            results=experts)


@views.route('/users/recent')
@login_required
def recent_users():
    '''
    Most recent users.
    '''
    users = User.query.order_by(desc(User.created_at)).limit(10).all()
    return render_template('search-results.html',
                           **{'title': 'Our most recent members', 'results': users,
                              'query': ''})


@views.route('/feedback')
def feedback():
    '''
    Feedback page.
    '''
    return render_template('feedback.html', **{})
