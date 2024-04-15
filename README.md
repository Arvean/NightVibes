# NightVibes

## Overview 
Night Vibes is a dynamic mobile app designed to enrich nightlife with real-time insights into the atmosphere, crowd sizes, and offerings of bars and clubs. It simplifies social outings by allowing users to see where friends are and effortlessly "ping" them for meetups, making it the quintessential tool for a seamless and enjoyable night out.

## Core Features:
- Live Updates & Ratings: Users at a venue can submit live updates on various factors affecting the nightlife experience, helping others make informed decisions about where to go.
- Friend Locator & Pings: Integrates social features allowing users to see if friends are at a bar or club and "ping" them to join, enhancing the social experience of going out.
- Geolocation-Based Venue Discovery: Users can find nearby bars and clubs with the best vibes, based on their current location and preferred criteria.
- Privacy-First Approach: Built with a focus on user privacy, offering robust controls over what information is shared and who it's shared with.

## Target Audience
Young adults and nightlife enthusiasts looking for a reliable guide to discover the best nightlife experiences, meet with friends, and explore new venues with confidence.

## Technology Stack:
Frontend: React Native for cross-platform mobile app development, ensuring a smooth, native-like user experience on both iOS and Android.
Backend: Python with Django or Flask frameworks for a robust, scalable server-side application capable of handling real-time data processing and updates.

## Objective: 
To become the go-to platform for nightlife exploration by offering up-to-date, user-generated content that accurately reflects the current state of bars and clubs, thereby ensuring users have the best possible night out.

## Getting Started:
Build the latest changes to the docker image:

`docker-compose build`

Start up the Django web and MySQL database services:

`docker-compose up`

or to run the services as background processes:

`docker-compose up -d`

Open another terminal and apply Django migrations to set up the database schema.
Note - If Django ORM is not being used by the application data this step is still 
necessary as Django still uses ORM for built-in apps (such as the authentication system).

`docker-compose exec web python manage.py migrate`

Create a superuser:
This step is necessary to access the Django admin panel. It only needs to be done once per database, unless the database is reset or recreated.

`docker-compose exec web python manage.py createsuperuser`

When done running the services:

`docker-compose down`

or if persisted database data (volumes) is desired to be removed:

`docker-compose down -v`

Note: Be sure to regularly prune unused containers, images, and volumes
as this can take up significant disk space over time:

`docker system prune`
