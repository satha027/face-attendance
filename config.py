import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

SECRET_KEY = os.environ.get('SECRET_KEY', 'class_skipper_super_secret_key_2026')
DATABASE_TYPE = os.environ.get('DATABASE_TYPE', 'sqlite')  # 'sqlite' or 'mysql'
SQLITE_DB_PATH = os.path.join(BASE_DIR, 'class_skipper.db')

MYSQL_CONFIG = {
    'host': os.environ.get('MYSQL_HOST', 'localhost'),
    'user': os.environ.get('MYSQL_USER', 'root'),
    'password': os.environ.get('MYSQL_PASSWORD', ''),
    'database': os.environ.get('MYSQL_DB', 'class_skipper'),
    'port': int(os.environ.get('MYSQL_PORT', 3306))
}

DATASET_DIR = os.path.join(BASE_DIR, 'static', 'dataset')
TRAINED_DIR = os.path.join(BASE_DIR, 'static', 'trained')
VIOLATIONS_DIR = os.path.join(BASE_DIR, 'static', 'violations')
STUDENT_PHOTOS_DIR = os.path.join(BASE_DIR, 'static', 'student_photos')

CASCADE_PATH = os.path.join(BASE_DIR, 'haarcascade_frontalface_default.xml')
MODEL_PATH = os.path.join(TRAINED_DIR, 'trainer.yml')

# Ensure necessary directories exist
for path in [DATASET_DIR, TRAINED_DIR, VIOLATIONS_DIR, STUDENT_PHOTOS_DIR]:
    os.makedirs(path, exist_ok=True)
