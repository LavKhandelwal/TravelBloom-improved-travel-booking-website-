TravelBloom: A full-stack travel booking demo built with HTML, CSS, JavaScript, Python, and SQLite.


TravelBloom brings multiple travel options into one interface: browse listings, compare options, create an account, complete a simulated checkout, manage bookings, and print an e-ticket voucher. The project uses a single-page frontend and a JSON API served by Python's standard library, with SQLite for persistent storage.


Project status: Educational/demo application. Payments are simulated; no real money is processed. Do not use this project to handle real bookings, credentials, or payments.

Inspiration: MakeMyTrip, Agoda



 Features:


Search and booking


- Browse six categories: Hotels, Flights, Trains, Buses, Cruises, and Holiday Packages.


- Search listings and compare up to four options side by side.


- Enter traveller details and proceed through a checkout page.


- Choose a simulated payment method: UPI, Card, or Net Banking.


- View bookings and payment status in My Trips.


- Cancel a confirmed booking; the app marks its payment as Refund initiated.


- View, print, or save an E-Ticket voucher as PDF through the browser's print dialog.


Accounts


- Register and log in using an email address or mobile number.


- Passwords on the Python backend are hashed with PBKDF2-HMAC-SHA256 using a per-user salt and 200,000 iterations.


- Token-based sessions expire after 30 days.


- Includes demo-only password reset and Google sign-in flows.


Admin and support


- Admin interface for adding and removing listings across the travel categories.


- Support ticket submission form.


User experience


- Multi-language interface options: English, हिन्दी, मराठी, Español, and Français.


- Browser-based Read Aloud accessibility feature.


- Responsive travel listing cards and booking flow.


Tech stack


[Layer	Technology]


Frontend	Vanilla HTML, CSS, and JavaScript in index.html


Backend	Python 3 http.server with ThreadingHTTPServer


API	JSON over HTTP


Database	SQLite 3 (sqlite3)


Sample data	seed.json


External assets/services	Unsplash images, Google Fonts, and MyMemory translation API



The backend uses only the Python standard library. No third-party Python packages are required.


- Project structure


TravelBloom/


├── server.py       # HTTP server, JSON API, authentication, and SQLite operations


├── index.html      # Single-page frontend (HTML, CSS, and JavaScript)


├── seed.json       # Sample travel listings loaded during initial setup


├── README.md       # Project documentation


└── travelbloom.db  # Created automatically on first run;  #not committed


Getting started:


Requirements


- Python 3.8 or newer


- A modern web browser


1. Clone the repository


Replace the URL and folder name with your GitHub repository details:


git clone https://github.com/<your-username>/<your-repository>.git


cd <your-repository>


Alternatively, download the repository ZIP and extract it.


2. Start the server


python server.py


Open http://localhost:8000 in your browser.


Important: Open the application through the server URL. Do not double-click index.html; account, booking, and payment flows rely on the backend.


3. Use a different port (optional)


macOS / Linux


PORT=5000 python server.py


Windows Command Prompt


set PORT=5000 && python server.py


Then visit http://localhost:5000.


Troubleshooting:


- Changes are not showing: stop any older running copy of server.py, restart the server, and hard-refresh the browser

- (Ctrl+Shift+R; on macOS, Cmd+Shift+R).

- Listings are not resetting: seed.json is read only when the database's items table is empty. To recreate the original sample data, stop the server and delete travelbloom.db. This deletes local users, bookings, tickets, and other stored application data too.


- Images or translations are missing: listing images, web fonts, and the MyMemory translation service require an internet connection.


Demo admin account:


On first startup, the server creates this administrator account if no admin user exists:


Field	Value


Email	admin@travelbloom.com


Password	Admin@123


Change the default password before sharing the application with anyone. This account is intended for local demonstration only.


Testing simulated payments


Checkout is a simulation, not a connection to a real payment processor.

[Payment method, Test input. Expected result]

Card, 4111 1111 1111 1111, Accepted

Card,	4000 0000 0000 0002,	Declined


UPI,	A syntactically valid ID, e.g. name@okbank,	Accepted by the demo validation

Net Banking,	SBI, HDFC Bank, ICICI Bank, Axis Bank, or Kotak Mahindra Bank,	Accepted by the demo validation


For card testing, in the future, enter a future expiry date (MM/YY), a 3- or 4-digit CVV, and a cardholder name. Card numbers are validated using the Luhn algorithm. The backend stores only the card brand and last four digits in the payment detail; it does not store the full card number or CVV.


Typical flow: select a listing → Continue to Payment → complete the simulated checkout → open My Trips → download the e-ticket or cancel the booking.


API overview


API endpoints use JSON and are served under /api. Authenticated endpoints expect:

Authorization: Bearer <token>


The token is returned by registration or login.

[Method	Endpoint	Access	Purpose]

POST	/api/register	Public	Create an account

POST	/api/login	Public	Log in using email or mobile number

POST	/api/google	Public	Demo Google sign-in

POST	/api/reset	Public	Demo password reset

GET	/api/items	Public	Retrieve travel listings

POST	/api/tickets	Public or logged-in	Submit a support ticket

GET	/api/me	User	Retrieve the current user

POST	/api/logout	User	End the current user's sessions

GET	/api/bookings	User	List the current user's bookings and payment details

POST	/api/checkout	User	Validate simulated payment and create a booking and payment record

POST	/api/bookings/cancel	User	Cancel a confirmed booking and mark its payment as refund initiated

POST	/api/items	Admin	Add a travel listing

DELETE	/api/items/<id>	Admin	Delete a travel listing



Database tables

The SQLite database contains these tables:

- users — user accounts, roles, and password hashes

- sessions — session tokens and creation times

- items — travel listings

- bookings — booking and traveller information

- payments — simulated payment records and statuses

- tickets — submitted support tickets

The server creates the database and tables automatically. It also attempts to add newer booking columns when upgrading an 
older database.


Sample data

seed.json contains sample listings for the travel categories. The seed file is loaded only when the database has no 
listings; editing it does not overwrite listings already stored in travelbloom.db.



To reload the original sample listings, stop the server and delete the local database file before restarting. This resets 
all local application data, not just listings.

Limitations and security notes

TravelBloom is a learning project and is not production-ready.

- No real payments: checkout validates test inputs and writes simulated payment records. It does not contact a bank or payment gateway, and cancellation only changes local statuses to “Refund initiated”; no money is refunded.


- Google sign-in is a demo stub: the endpoint signs in a shared demo account; it does not perform Google OAuth.

- Password reset is not secure: there is no email verification or reset-token flow. Anyone who knows an account's email may be able to set a new password.

- HTTP only: the development server does not provide HTTPS.


- Permissive CORS: the backend allows requests from any origin (*).

- Built-in server: Python's http.server is suitable for development and demonstration, not as a hardened production server.

- External dependencies at runtime: images and web fonts are fetched online; translation relies on the free MyMemory API.

- Default admin credentials: the initial admin password is public in this README and must not be used in a real deployment.
Before any real deployment, use a production-grade server over HTTPS, restrict CORS, implement secure account recovery and real OAuth, integrate a trusted payment provider, review authentication/session handling, and perform a security review.


