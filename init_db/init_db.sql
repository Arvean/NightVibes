"Beginning will initialize the databases and create the framework."

CREATE TABLE IF NOT EXISTS users (
    user_id INT PRIMARY KEY NOT NULL,
    user_name CHAR(255),
    customer_name CHAR(255),
    email_address CHAR (255),
    password_hashed CHAR (255),
    location_sharing BOOLEAN,
    phone_number CHAR(25),
    gender CHAR(10)

);

CREATE TABLE IF NOT EXISTS venues (
    venue_id INT PRIMARY KEY NOT NULL,
    venue_name CHAR(255),
    venue_address CHAR(255),
    venue_city CHAR(255),
    venue_state CHAR(100),
    venue_type CHAR(50),
    phone_number CHAR(25)
);

CREATE TABLE IF NOT EXISTS friends (
    friendship_id INT PRIMARY KEY NOT NULL,
    user1_id INT,
    user2_id INT,
    friendship_status CHAR(50),
    request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    accept_date TIMESTAMP,
    FOREIGN KEY (user1_id) REFERENCES users(user_id),
    FOREIGN KEY (user2_id) REFERENCES users(user_id),
    CONSTRAINT check_user_ids CHECK (user1_id <> user2_id)

);

CREATE TABLE IF NOT EXISTS location_pings (
    ping_id INT PRIMARY KEY NOT NULL,
    requestor_id INT,
    responder_id INT,
    location_id INT,
    ping_type CHAR(50),
    ping_status CHAR(50),
    request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    response_date TIMESTAMP,
    ping_details CHAR(100),
    FOREIGN KEY (requestor_id) REFERENCES users(user_id),
    FOREIGN KEY (responder_id) REFERENCES users(user_id),
    FOREIGN KEY (location_id) REFERENCES venues(venue_id)
);

CREATE TABLE IF NOT EXISTS notifications (
    notification_id INT PRIMARY KEY NOT NULL,
    user_id INT,
    notification_type CHAR(100),
    notification_content CHAR(255),
    notification_status CHAR(50),
    notified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS user_venue_interaction (
    interaction_id INT PRIMARY KEY NOT NULL,
    user_id INT,
    venue_id INT,
    number_of_people INT,
    overall_rating INT,
    gender_diversity_rating INT,
    interaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (venue_id) REFERENCES venues(venue_id)
);

" Now we add fake data from USER_DATA.csv and VENUE_DATA.csv to the users & venue data tables"

"Users"
LOAD DATA INFILE 'USER_DATA.csv'
INTO TABLE users
FIELDS TERMINATED BY ','
ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS;

"Venues"
LOAD DATA INFILE 'VENUE_DATA.csv'
INTO TABLE venues
FIELDS TERMINATED BY ','
ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS;





