from flask import Blueprint, render_template
from flask_login import login_required

scanner_bp = Blueprint('scanner', __name__, url_prefix='/scanner')


@scanner_bp.route('/')
@login_required
def index():
    """Scanner main page - Coming Soon"""
    return render_template('scanner/index.html', title='Stock Scanner')
