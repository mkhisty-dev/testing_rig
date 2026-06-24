const express = require('express');
const app = express();
const PORT = 3000;

app.use(express.json());

const CORRECT_TOKEN = "secret-group-token-123";

app.post('/validate-token', (req, res) => {
    const userToken = req.body.token;
    if (userToken === CORRECT_TOKEN) {
        return res.json({ valid: true });
    } else {
        return res.json({ valid: false });
    }
});

app.listen(PORT, () => {
    console.log(`Auth microservice running on http://localhost:${PORT}`);
});
