// Reads the passenger's start PIN of the active ride from the QA API (Maestro's GraalJS: `http` and `json`).
const login = http.post(`${API_URL}/auth/login`, {
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: PASSENGER_EMAIL, password: PASSENGER_PASSWORD }),
});
const token = json(login.body).access_token;
const ride = json(http.get(`${API_URL}/rides/active`, { headers: { Authorization: `Bearer ${token}` } }).body);
output.pin = ride && ride.start_pin ? ride.start_pin : '';
