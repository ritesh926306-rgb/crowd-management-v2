-- ===============================================================
-- VenueGuard — Smart Crowd Control Management System
-- Production Database Schema (v4.0)
-- 10 Unified Tables: Admin Users, Guard Users, Events, Registrations,
-- Group Members, QR Tokens, Entry/Exit Logs, Emergency Records,
-- Notifications, and Activity Audit Logs.
-- ===============================================================

CREATE DATABASE IF NOT EXISTS `venue_crowd` 
  CHARACTER SET utf8mb4 
  COLLATE utf8mb4_unicode_ci;

USE `venue_crowd`;

-- ---------------------------------------------------------------
-- 1. Table: admin_users
-- Authorized administrators for central venue command control
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `admin_users` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `username` VARCHAR(64) NOT NULL UNIQUE,
    `password_hash` VARCHAR(255) NOT NULL,
    `full_name` VARCHAR(100) NOT NULL DEFAULT 'Administrator',
    `role` VARCHAR(50) NOT NULL DEFAULT 'SUPERADMIN',
    `is_active` TINYINT(1) NOT NULL DEFAULT 1,
    `created_at` DATETIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------
-- 2. Table: guard_accounts
-- Multi-guard account management with gate assignments and permissions
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `guard_accounts` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `username` VARCHAR(64) NOT NULL UNIQUE,
    `password_hash` VARCHAR(255) NOT NULL,
    `full_name` VARCHAR(100) NOT NULL,
    `assigned_gate` VARCHAR(50) NOT NULL DEFAULT 'all',
    `permissions` VARCHAR(255) NOT NULL DEFAULT 'scan,lookup,checkout',
    `is_active` TINYINT(1) NOT NULL DEFAULT 1,
    `last_active_at` DATETIME NULL DEFAULT NULL,
    `created_at` DATETIME NOT NULL,
    INDEX `idx_guard_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------
-- 3. Table: events
-- Complete event management: date, time, location, capacity, status
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `events` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `title` VARCHAR(255) NOT NULL,
    `event_date` VARCHAR(50) NOT NULL,
    `event_time` VARCHAR(50) NOT NULL DEFAULT '09:00 AM - 09:00 PM',
    `location` VARCHAR(255) NOT NULL,
    `description` TEXT NULL,
    `banner_url` TEXT NULL,
    `max_capacity` INT UNSIGNED NOT NULL DEFAULT 1000,
    `expected_population` INT UNSIGNED NOT NULL DEFAULT 500,
    `is_registration_active` TINYINT(1) NOT NULL DEFAULT 1,
    `status` VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    `created_at` DATETIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------
-- 4. Table: registrations
-- Master visitor records with unique Visitor ID, QR signature & status
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `registrations` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `event_id` BIGINT UNSIGNED NOT NULL DEFAULT 1,
    `visitor_id` VARCHAR(64) NOT NULL UNIQUE,
    `reg_code` VARCHAR(64) NOT NULL UNIQUE,
    `language` VARCHAR(10) NOT NULL DEFAULT 'en',
    `primary_name` VARCHAR(255) NOT NULL,
    `mobile` VARCHAR(20) NOT NULL,
    `age` INT UNSIGNED NOT NULL,
    `address` TEXT NULL,
    `group_count` INT UNSIGNED NOT NULL DEFAULT 1,
    `assigned_group` VARCHAR(50) NOT NULL,
    `assigned_gate` VARCHAR(100) NOT NULL,
    `gate_id` VARCHAR(50) NOT NULL,
    `hmac_signature` VARCHAR(128) NOT NULL,
    `qr_token` VARCHAR(128) NULL,
    `status` VARCHAR(20) NOT NULL DEFAULT 'VALID', -- VALID, CHECKED_IN, CANCELLED
    `checked_in` TINYINT(1) NOT NULL DEFAULT 0,
    `checked_in_at` DATETIME NULL DEFAULT NULL,
    `checked_out` TINYINT(1) NOT NULL DEFAULT 0,
    `checked_out_at` DATETIME NULL DEFAULT NULL,
    `scan_attempts` INT UNSIGNED NOT NULL DEFAULT 0,
    `created_at` DATETIME NOT NULL,
    INDEX `idx_reg_code` (`reg_code`),
    INDEX `idx_visitor_id` (`visitor_id`),
    INDEX `idx_mobile` (`mobile`),
    INDEX `idx_status` (`status`),
    INDEX `idx_checked_in` (`checked_in`),
    INDEX `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------
-- 5. Table: group_members
-- Accompanying family / group member details
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `group_members` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `reg_id` BIGINT UNSIGNED NOT NULL,
    `member_name` VARCHAR(255) NOT NULL,
    `member_age` INT UNSIGNED NOT NULL,
    `member_mobile` VARCHAR(20) NULL DEFAULT '',
    INDEX `idx_reg_id` (`reg_id`),
    CONSTRAINT `fk_group_members_reg` 
        FOREIGN KEY (`reg_id`) 
        REFERENCES `registrations` (`id`) 
        ON DELETE CASCADE 
        ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------
-- 6. Table: qr_tokens
-- Secure dynamic tokens linked to registrations
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `qr_tokens` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `reg_code` VARCHAR(64) NOT NULL,
    `token` VARCHAR(128) NOT NULL UNIQUE,
    `is_revoked` TINYINT(1) NOT NULL DEFAULT 0,
    `created_at` DATETIME NOT NULL,
    INDEX `idx_qr_token` (`token`),
    INDEX `idx_qr_reg_code` (`reg_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------
-- 7. Table: entry_exit_logs
-- Verified transactions for accurate live occupancy tracking
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `entry_exit_logs` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `reg_code` VARCHAR(64) NOT NULL,
    `action` ENUM('ENTRY', 'EXIT') NOT NULL,
    `headcount` INT UNSIGNED NOT NULL DEFAULT 1,
    `gate_id` VARCHAR(50) NOT NULL,
    `guard_id` VARCHAR(64) NOT NULL DEFAULT 'guard_default',
    `guard_name` VARCHAR(100) NOT NULL DEFAULT 'Duty Guard',
    `timestamp` DATETIME NOT NULL,
    INDEX `idx_log_reg_code` (`reg_code`),
    INDEX `idx_log_action` (`action`),
    INDEX `idx_log_timestamp` (`timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------
-- 8. Table: emergency_events
-- Incident records for emergency mode activations and resolutions
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `emergency_events` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `status` VARCHAR(20) NOT NULL DEFAULT 'NORMAL',
    `reason` TEXT NOT NULL,
    `activated_by` VARCHAR(100) NOT NULL,
    `activated_at` DATETIME NOT NULL,
    `resolved_at` DATETIME NULL DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------
-- 9. Table: notifications
-- System broadcast notifications for visitors and guard terminals
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `notifications` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `title` VARCHAR(255) NOT NULL,
    `message` TEXT NOT NULL,
    `target` VARCHAR(50) NOT NULL DEFAULT 'ALL', -- ALL, GUARDS, VISITORS
    `is_read` TINYINT(1) NOT NULL DEFAULT 0,
    `created_at` DATETIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------
-- 10. Table: audit_logs
-- Security audit logging for administrative actions, edits, and alerts
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `audit_logs` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `actor` VARCHAR(100) NOT NULL,
    `action` VARCHAR(100) NOT NULL,
    `details` TEXT NULL,
    `ip_address` VARCHAR(45) NULL,
    `timestamp` DATETIME NOT NULL,
    INDEX `idx_audit_timestamp` (`timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------
-- 11. Table: system_settings
-- Key-value administrative store (event capacity, security params)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `system_settings` (
    `setting_key` VARCHAR(100) NOT NULL PRIMARY KEY,
    `setting_value` TEXT NOT NULL,
    `updated_at` DATETIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------
-- View: Gate Congestion Summary
-- ---------------------------------------------------------------
CREATE OR REPLACE VIEW `v_gate_congestion` AS
SELECT 
    gate_id,
    assigned_gate,
    assigned_group,
    COUNT(id) AS total_groups,
    COALESCE(SUM(group_count), 0) AS total_headcount,
    COALESCE(SUM(CASE WHEN checked_in = 1 AND checked_out = 0 THEN group_count ELSE 0 END), 0) AS current_occupancy,
    COALESCE(SUM(CASE WHEN checked_in = 1 THEN group_count ELSE 0 END), 0) AS admitted_headcount,
    COALESCE(SUM(CASE WHEN checked_out = 1 THEN group_count ELSE 0 END), 0) AS exited_headcount
FROM `registrations`
WHERE status != 'CANCELLED'
GROUP BY gate_id, assigned_gate, assigned_group;
