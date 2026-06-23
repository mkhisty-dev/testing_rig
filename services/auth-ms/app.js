const express = require('express');
const app = express();
const PORT = 3000;

// Middleware to parse JSON bodies
app.use(express.json());

// correct token that we will validate against
const CORRECT_TOKEN = "secret-group-token-123";

// API endpoint
app.post('/validate-token', (req, res) => {
    const userToken = req.body.token;

    // Check if the token matches our hardcoded value
    if (userToken === CORRECT_TOKEN) {
        return res.json({ valid: true });
    } else {
        return res.json({ valid: false });
    }
});

app.listen(PORT, () => {
    console.log(`Auth microservice running on http://localhost:${PORT}`);
});
