"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('role', sa.String(20), nullable=False, default='student'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('camera_consent', sa.Boolean(), default=False),
        sa.Column('geolocation_consent', sa.Boolean(), default=False),
        sa.Column('face_embedding_hash', sa.String(64), nullable=True),
        sa.Column('face_enrolled', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.Column('scheduled_deletion_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_role', 'users', ['role'])
    op.create_index('ix_users_is_active', 'users', ['is_active'])

    # Create courses table
    op.create_table(
        'courses',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('code', sa.String(20), unique=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('semester', sa.String(20), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('instructor_id', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('venue_latitude', sa.Float(), nullable=True),
        sa.Column('venue_longitude', sa.Float(), nullable=True),
        sa.Column('venue_name', sa.String(255), nullable=True),
        sa.Column('geofence_radius_meters', sa.Float(), default=100.0),
        sa.Column('require_face_recognition', sa.Boolean(), default=False),
        sa.Column('require_device_binding', sa.Boolean(), default=True),
        sa.Column('risk_threshold', sa.Float(), default=0.5),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_courses_code', 'courses', ['code'])
    op.create_index('ix_courses_semester', 'courses', ['semester'])
    op.create_index('ix_courses_is_active', 'courses', ['is_active'])

    # Create enrollments table
    op.create_table(
        'enrollments',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('student_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('course_id', sa.String(36), sa.ForeignKey('courses.id'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('enrolled_at', sa.DateTime(), nullable=False),
        sa.Column('dropped_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('student_id', 'course_id', name='uq_student_course'),
    )
    op.create_index('ix_enrollments_student_id', 'enrollments', ['student_id'])
    op.create_index('ix_enrollments_course_id', 'enrollments', ['course_id'])

    # Create sessions table
    op.create_table(
        'sessions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('course_id', sa.String(36), sa.ForeignKey('courses.id'), nullable=False),
        sa.Column('instructor_id', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('session_type', sa.String(50), default='lecture'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('scheduled_start', sa.DateTime(), nullable=False),
        sa.Column('scheduled_end', sa.DateTime(), nullable=False),
        sa.Column('checkin_opens_at', sa.DateTime(), nullable=False),
        sa.Column('checkin_closes_at', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, default='scheduled'),
        sa.Column('actual_start', sa.DateTime(), nullable=True),
        sa.Column('actual_end', sa.DateTime(), nullable=True),
        sa.Column('venue_latitude', sa.Float(), nullable=True),
        sa.Column('venue_longitude', sa.Float(), nullable=True),
        sa.Column('venue_name', sa.String(255), nullable=True),
        sa.Column('geofence_radius_meters', sa.Float(), nullable=True),
        sa.Column('require_liveness_check', sa.Boolean(), default=True),
        sa.Column('require_face_match', sa.Boolean(), default=False),
        sa.Column('risk_threshold', sa.Float(), nullable=True),
        sa.Column('qr_code_secret', sa.String(64), nullable=True),
        sa.Column('qr_code_expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_sessions_course_id', 'sessions', ['course_id'])
    op.create_index('ix_sessions_status', 'sessions', ['status'])
    op.create_index('ix_sessions_scheduled_start', 'sessions', ['scheduled_start'])

    # Create devices table
    op.create_table(
        'devices',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('device_fingerprint', sa.String(64), unique=True, nullable=False),
        sa.Column('device_name', sa.String(255), nullable=True),
        sa.Column('platform', sa.String(50), nullable=True),
        sa.Column('browser', sa.String(100), nullable=True),
        sa.Column('os_version', sa.String(50), nullable=True),
        sa.Column('app_version', sa.String(50), nullable=True),
        sa.Column('public_key', sa.Text(), nullable=True),
        sa.Column('public_key_created_at', sa.DateTime(), nullable=True),
        sa.Column('public_key_expires_at', sa.DateTime(), nullable=True),
        sa.Column('attestation_passed', sa.Boolean(), default=False),
        sa.Column('last_attestation_at', sa.DateTime(), nullable=True),
        sa.Column('attestation_token', sa.Text(), nullable=True),
        sa.Column('is_trusted', sa.Boolean(), default=False),
        sa.Column('trust_score', sa.String(20), default='low'),
        sa.Column('is_emulator', sa.Boolean(), default=False),
        sa.Column('is_rooted_jailbroken', sa.Boolean(), default=False),
        sa.Column('first_seen_at', sa.DateTime(), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(), nullable=False),
        sa.Column('total_checkins', sa.Integer(), default=0),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('revocation_reason', sa.Text(), nullable=True),
    )
    op.create_index('ix_devices_user_id', 'devices', ['user_id'])
    op.create_index('ix_devices_device_fingerprint', 'devices', ['device_fingerprint'])
    op.create_index('ix_devices_is_active', 'devices', ['is_active'])
    op.create_index('ix_devices_is_trusted', 'devices', ['is_trusted'])

    # Create checkins table
    op.create_table(
        'checkins',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('sessions.id'), nullable=False),
        sa.Column('student_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('device_id', sa.String(36), sa.ForeignKey('devices.id'), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, default='pending'),
        sa.Column('checked_in_at', sa.DateTime(), nullable=False),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('location_accuracy_meters', sa.Float(), nullable=True),
        sa.Column('distance_from_venue_meters', sa.Float(), nullable=True),
        sa.Column('liveness_passed', sa.Boolean(), nullable=True),
        sa.Column('liveness_score', sa.Float(), nullable=True),
        sa.Column('liveness_challenge_type', sa.String(50), nullable=True),
        sa.Column('face_match_passed', sa.Boolean(), nullable=True),
        sa.Column('face_match_score', sa.Float(), nullable=True),
        sa.Column('face_embedding_hash', sa.String(64), nullable=True),
        sa.Column('risk_score', sa.Float(), nullable=False, default=0.0),
        sa.Column('risk_factors', sa.Text(), nullable=True),
        sa.Column('qr_code_verified', sa.Boolean(), default=False),
        sa.Column('reviewed_by_id', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('appeal_reason', sa.Text(), nullable=True),
        sa.Column('appealed_at', sa.DateTime(), nullable=True),
        sa.Column('scheduled_deletion_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('session_id', 'student_id', name='uq_session_student'),
    )
    op.create_index('ix_checkins_session_id', 'checkins', ['session_id'])
    op.create_index('ix_checkins_student_id', 'checkins', ['student_id'])
    op.create_index('ix_checkins_status', 'checkins', ['status'])
    op.create_index('ix_checkins_checked_in_at', 'checkins', ['checked_in_at'])
    op.create_index('ix_checkins_risk_score', 'checkins', ['risk_score'])

    # Create risk_signals table
    op.create_table(
        'risk_signals',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('checkin_id', sa.String(36), sa.ForeignKey('checkins.id'), nullable=False),
        sa.Column('signal_type', sa.String(50), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False, default=1.0),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('weight', sa.Float(), nullable=False, default=0.1),
        sa.Column('detected_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_risk_signals_checkin_id', 'risk_signals', ['checkin_id'])
    op.create_index('ix_risk_signals_signal_type', 'risk_signals', ['signal_type'])
    op.create_index('ix_risk_signals_severity', 'risk_signals', ['severity'])
    op.create_index('ix_risk_signals_detected_at', 'risk_signals', ['detected_at'])

    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=True),
        sa.Column('resource_id', sa.String(36), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('device_id', sa.String(36), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('success', sa.Boolean(), default=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'])
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_logs_timestamp', 'audit_logs', ['timestamp'])
    op.create_index('ix_audit_logs_ip_address', 'audit_logs', ['ip_address'])


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('risk_signals')
    op.drop_table('checkins')
    op.drop_table('devices')
    op.drop_table('sessions')
    op.drop_table('enrollments')
    op.drop_table('courses')
    op.drop_table('users')
