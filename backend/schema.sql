-- ===============================================================
-- Venue Entry & Smart Crowd Management System
-- MySQL & PostgreSQL Production Database Schema (v3.0)
-- Optimized for ACID transactions, role-based security, & audit trails
-- ===============================================================

CREATE DATABASE IF NOT EXISTS `venue_crowd` 
  CHARACTER SET utf8mb4 
  COLLATE utf8mb4_unicode_ci;

USE `venue_crowd`;

-- ---------------------------------------------------------------
-- 1. Table: registrations
-- Stores master visitor registration pass records
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `registrations` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `reg_code` VARCHAR(64) NOT NULL UNIQUE,
    `language` VARCHAR(10) NOT NULL DEFAULT 'en',
    `primary_name` VARCHAR(255) NOT NULL,
    `mobile` VARCHAR(20) NOT NULL,
    `age` INT UNSIGNED NOT NULL,
    `address` TEXT NOT NULL,
    `group_count` INT UNSIGNED NOT NULL DEFAULT 1,
    `assigned_group` VARCHAR(50) NOT NULL,
    `assigned_gate` VARCHAR(100) NOT NULL,
    `gate_id` VARCHAR(50) NOT NULL,
    `hmac_signature` VARCHAR(128) NOT NULL,
    `created_at` DATETIME NOT NULL,
    `checked_in` TINYINT(1) NOT NULL DEFAULT 0,
    `checked_in_at` DATETIME NULL DEFAULT NULL,
    `checked_out` TINYINT(1) NOT NULL DEFAULT 0,
    `checked_out_at` DATETIME NULL DEFAULT NULL,
    INDEX `idx_reg_code` (`reg_code`),
    INDEX `idx_gate_id` (`gate_id`),
    INDEX `idx_checked_in` (`checked_in`),
    INDEX `idx_checked_out` (`checked_out`),
    INDEX `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------
-- 2. Table: group_members
-- Stores accompanying family/group member details
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
-- 3. Table: system_settings
-- Stores administrative settings like capacity, event info, dynamic security
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `system_settings` (
    `setting_key` VARCHAR(100) NOT NULL PRIMARY KEY,
    `setting_value` TEXT NOT NULL,
    `updated_at` DATETIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------
-- 4. Table: guard_accounts
-- Multi-guard account management with gate assignments
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `guard_accounts` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `username` VARCHAR(64) NOT NULL UNIQUE,
    `password_hash` VARCHAR(255) NOT NULL,
    `full_name` VARCHAR(100) NOT NULL,
    `assigned_gate` VARCHAR(50) NOT NULL DEFAULT 'all',
    `is_active` TINYINT(1) NOT NULL DEFAULT 1,
    `created_at` DATETIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------
-- 5. Table: entry_exit_logs
-- Verified entry and exit transactions for accurate occupancy tracking
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `entry_exit_logs` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `reg_code` VARCHAR(64) NOT NULL,
    `action` ENUM('ENTRY', 'EXIT') NOT NULL,
    `headcount` INT UNSIGNED NOT NULL DEFAULT 1,
    `gate_id` VARCHAR(50) NOT NULL,
    `guard_name` VARCHAR(100) NOT NULL DEFAULT 'System Guard',
    `timestamp` DATETIME NOT NULL,
    INDEX `idx_log_reg_code` (`reg_code`),
    INDEX `idx_log_action` (`action`),
    INDEX `idx_log_timestamp` (`timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------
-- 6. Table: audit_logs
-- Security audit logging for administrative actions and alerts
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
-- 7. Table: emergency_events
-- Records emergency mode activations and resolutions
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
-- 8. Gate Congestion Summary View
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
GROUP BY gate_id, assigned_gate, assigned_group;
