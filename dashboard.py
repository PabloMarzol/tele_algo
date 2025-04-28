import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
import polars as pl
from datetime import datetime, timedelta
import json
import plotly
import plotly.express as px
from functools import wraps
import pandas as pd

# Import database manager
from db_manager import TradingBotDatabase
from config import Config

# Initialize app
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Load configuration
config = Config()
db = TradingBotDatabase(data_dir=config.get('data_dir'))

# Admin authentication
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        # Simple admin password verification (for demo purposes)
        # In production, use a more secure authentication method
        if password == config.get('admin_password', 'admin123'):
            session['admin'] = True
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid password')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('login'))

@app.route('/')
@admin_required
def dashboard():
    # Get stats for dashboard
    total_users = db.users_df.height
    verified_users = db.users_df.filter(pl.col("is_verified") == True).height
    active_users_7d = db.get_active_users(days=7)
    
    # Convert Polars dataframe to Pandas for Plotly compatibility
    users_pandas = db.users_df.to_pandas()
    
    # Create visualizations
    risk_distribution = None
    deposit_distribution = None
    user_growth = None
    
    if total_users > 0:
        # Risk appetite distribution
        if 'risk_appetite' in users_pandas.columns:
            risk_data = users_pandas[~users_pandas['risk_appetite'].isna()]
            if len(risk_data) > 0:
                fig = px.histogram(risk_data, x='risk_appetite', 
                                  title='Risk Appetite Distribution',
                                  labels={'risk_appetite': 'Risk Appetite (1-10)', 'count': 'Number of Users'},
                                  color_discrete_sequence=['#3366CC'])
                risk_distribution = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        
        # Deposit amount distribution
        if 'deposit_amount' in users_pandas.columns:
            deposit_data = users_pandas[~users_pandas['deposit_amount'].isna()]
            if len(deposit_data) > 0:
                fig = px.histogram(deposit_data, x='deposit_amount', 
                                  title='Deposit Amount Distribution',
                                  labels={'deposit_amount': 'Deposit Amount ($)', 'count': 'Number of Users'},
                                  color_discrete_sequence=['#33CC36'])
                deposit_distribution = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        
        # User growth over time
        if 'join_date' in users_pandas.columns:
            # Convert join_date to datetime
            users_pandas['join_date'] = pd.to_datetime(users_pandas['join_date'])
            # Group by day and count users
            user_growth_data = users_pandas.groupby(users_pandas['join_date'].dt.date).size().reset_index(name='count')
            user_growth_data.columns = ['date', 'new_users']
            # Calculate cumulative sum
            user_growth_data['total_users'] = user_growth_data['new_users'].cumsum()
            
            fig = px.line(user_growth_data, x='date', y='total_users', 
                         title='User Growth Over Time',
                         labels={'date': 'Date', 'total_users': 'Total Users'},
                         color_discrete_sequence=['#CC3366'])
            user_growth = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    
    return render_template('dashboard.html', 
                          total_users=total_users,
                          verified_users=verified_users,
                          active_users=active_users_7d,
                          risk_distribution=risk_distribution,
                          deposit_distribution=deposit_distribution,
                          user_growth=user_growth)

@app.route('/users')
@admin_required
def users():
    # Get users data
    users_data = db.users_df.to_pandas()
    
    # Sort by join date (newest first)
    if 'join_date' in users_data.columns:
        users_data['join_date'] = pd.to_datetime(users_data['join_date'])
        users_data = users_data.sort_values(by='join_date', ascending=False)
    
    return render_template('users.html', users=users_data)

@app.route('/messages')
@admin_required
def messages():
    # Get current messages
    welcome_msg = db.get_setting("welcome_message", config.get('messages.welcome'))
    periodic_msg = db.get_setting("periodic_message", config.get('messages.periodic'))
    private_welcome_msg = db.get_setting("private_welcome_message", config.get('messages.private_welcome'))
    
    return render_template('messages.html', 
                          welcome_msg=welcome_msg,
                          periodic_msg=periodic_msg,
                          private_welcome_msg=private_welcome_msg)

@app.route('/update_messages', methods=['POST'])
@admin_required
def update_messages():
    # Update messages
    welcome_msg = request.form.get('welcome_msg')
    periodic_msg = request.form.get('periodic_msg')
    private_welcome_msg = request.form.get('private_welcome_msg')
    
    # Save to database
    db.update_setting("welcome_message", welcome_msg)
    db.update_setting("periodic_message", periodic_msg)
    db.update_setting("private_welcome_message", private_welcome_msg)
    
    flash('Messages updated successfully')
    return redirect(url_for('messages'))

@app.route('/settings')
@admin_required
def settings():
    # Get current settings
    interval_hours = db.get_setting("message_interval_hours", config.get('message_interval_hours'))
    captcha_enabled = db.get_setting("captcha_enabled", config.get('auth.captcha_enabled'))
    max_attempts = db.get_setting("max_auth_attempts", config.get('auth.max_attempts'))
    
    return render_template('settings.html',
                          interval_hours=interval_hours,
                          captcha_enabled=captcha_enabled,
                          max_attempts=max_attempts)

@app.route('/update_settings', methods=['POST'])
@admin_required
def update_settings():
    # Update settings
    interval_hours = request.form.get('interval_hours', type=int)
    captcha_enabled = 'captcha_enabled' in request.form
    max_attempts = request.form.get('max_attempts', type=int)
    
    # Save to database
    db.update_setting("message_interval_hours", interval_hours)
    db.update_setting("captcha_enabled", captcha_enabled)
    db.update_setting("max_auth_attempts", max_attempts)
    
    flash('Settings updated successfully')
    return redirect(url_for('settings'))

# Run the app
if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    # Create simple templates for demo
    with open('templates/login.html', 'w') as f:
        f.write('''
<!DOCTYPE html>
<html>
<head>
    <title>Admin Login</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    <div class="container mt-5">
        <div class="row justify-content-center">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h3 class="text-center">Trading Bot Admin</h3>
                    </div>
                    <div class="card-body">
                        {% with messages = get_flashed_messages() %}
                            {% if messages %}
                                {% for message in messages %}
                                    <div class="alert alert-danger">{{ message }}</div>
                                {% endfor %}
                            {% endif %}
                        {% endwith %}
                        <form method="post">
                            <div class="mb-3">
                                <label for="password" class="form-label">Admin Password</label>
                                <input type="password" class="form-control" id="password" name="password" required>
                            </div>
                            <div class="d-grid">
                                <button type="submit" class="btn btn-primary">Login</button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
        ''')
    
    with open('templates/dashboard.html', 'w') as f:
        f.write('''
<!DOCTYPE html>
<html>
<head>
    <title>Admin Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="#">Trading Bot Admin</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav">
                    <li class="nav-item">
                        <a class="nav-link active" href="{{ url_for('dashboard') }}">Dashboard</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('users') }}">Users</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('messages') }}">Messages</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('settings') }}">Settings</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('logout') }}">Logout</a>
                    </li>
                </ul>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        <h1>Dashboard</h1>
        
        <div class="row mt-4">
            <div class="col-md-4">
                <div class="card text-white bg-primary mb-3">
                    <div class="card-header">Total Users</div>
                    <div class="card-body">
                        <h5 class="card-title">{{ total_users }}</h5>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card text-white bg-success mb-3">
                    <div class="card-header">Verified Users</div>
                    <div class="card-body">
                        <h5 class="card-title">{{ verified_users }}</h5>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card text-white bg-info mb-3">
                    <div class="card-header">Active Users (7 days)</div>
                    <div class="card-body">
                        <h5 class="card-title">{{ active_users }}</h5>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="row mt-4">
            {% if user_growth %}
            <div class="col-md-12 mb-4">
                <div class="card">
                    <div class="card-body">
                        <div id="user-growth"></div>
                    </div>
                </div>
            </div>
            {% endif %}
            
            {% if risk_distribution %}
            <div class="col-md-6 mb-4">
                <div class="card">
                    <div class="card-body">
                        <div id="risk-distribution"></div>
                    </div>
                </div>
            </div>
            {% endif %}
            
            {% if deposit_distribution %}
            <div class="col-md-6 mb-4">
                <div class="card">
                    <div class="card-body">
                        <div id="deposit-distribution"></div>
                    </div>
                </div>
            </div>
            {% endif %}
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    
    {% if user_growth %}
    <script>
        var userGrowthData = {{ user_growth|safe }};
        Plotly.newPlot('user-growth', userGrowthData.data, userGrowthData.layout);
    </script>
    {% endif %}
    
    {% if risk_distribution %}
    <script>
        var riskData = {{ risk_distribution|safe }};
        Plotly.newPlot('risk-distribution', riskData.data, riskData.layout);
    </script>
    {% endif %}
    
    {% if deposit_distribution %}
    <script>
        var depositData = {{ deposit_distribution|safe }};
        Plotly.newPlot('deposit-distribution', depositData.data, depositData.layout);
    </script>
    {% endif %}
</body>
</html>
        ''')
    
    # Create similar templates for other pages...
    
    app.run(debug=True, port=5000)