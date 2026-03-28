const express = require('express');
const cors = require('cors');
const { createClient } = require('@supabase/supabase-js');
const authRoutes = require('./routes/auth');
const teamsRoutes = require('./routes/teams');
const campaignsRoutes = require('./routes/campaigns');

const app = express();
const PORT = process.env.PORT || 3847;

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY) {
  console.error('[cloud] Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY env vars');
  process.exit(1);
}

const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);

// C6: CORS with explicit origin whitelist
const allowedOrigins = (process.env.CORS_ORIGINS || 'http://localhost:8847,http://localhost:3000').split(',');
app.use(cors({
  origin: function (origin, callback) {
    // Allow requests with no origin (CLI tools, server-to-server)
    if (!origin || allowedOrigins.includes(origin)) return callback(null, true);
    callback(null, false);
  }
}));

// M2: reduce JSON body limit from 50mb to 1mb
app.use(express.json({ limit: '1mb' }));

// H11: security headers
app.use((req, res, next) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('X-XSS-Protection', '1; mode=block');
  res.setHeader('Referrer-Policy', 'no-referrer');
  next();
});

app.use((req, res, next) => {
  req.supabase = supabase;
  next();
});

app.use('/api/auth', authRoutes);
app.use('/api/teams', teamsRoutes);
app.use('/api/campaigns', campaignsRoutes);

app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', service: 'marketing-pipeline-cloud' });
});

const server = app.listen(PORT, () => {
  console.log(`[cloud] Marketing Pipeline API running on port ${PORT}`);
});

// L2: graceful shutdown
function shutdown() {
  console.log('[cloud] Shutting down gracefully...');
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(1), 5000);
}
process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);

module.exports = app;
