CREATE DATABASE IF NOT EXISTS luna_fsq CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'luna'@'localhost' IDENTIFIED BY 'luna_pass_change_me';
GRANT ALL PRIVILEGES ON luna_fsq.* TO 'luna'@'localhost';
FLUSH PRIVILEGES;
