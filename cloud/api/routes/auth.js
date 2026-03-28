const { Router } = require('express');
const crypto = require('crypto');
const { authMiddleware } = require('../middleware/auth');
const router = Router();

// POST /api/auth/register
router.post('/register', async (req, res) => {
  const { email, display_name, password } = req.body;
  if (!email || !display_name) {
    return res.status(400).json({ error: 'email and display_name required' });
  }

  // Check if caller is an authenticated team owner/admin (has valid x-api-key + admin role)
  const apiKey = req.headers['x-api-key'];
  let isAdmin = false;
  if (apiKey) {
    const { data: caller } = await req.supabase
      .from('users')
      .select('id')
      .eq('api_key', apiKey)
      .single();
    if (caller) {
      // Verify the caller is an owner or admin of at least one team
      const { data: adminRole } = await req.supabase
        .from('team_members')
        .select('role')
        .eq('user_id', caller.id)
        .in('role', ['owner', 'admin'])
        .limit(1)
        .single();
      if (adminRole) isAdmin = true;
    }
  }

  // Self-registration (no valid admin API key) requires the correct password
  if (!isAdmin) {
    const regPassword = process.env.REGISTRATION_PASSWORD;
    if (!regPassword) {
      return res.status(403).json({ error: 'Self-registration is not configured. Contact an admin.' });
    }
    if (!password || password !== regPassword) {
      return res.status(403).json({ error: 'Invalid registration password' });
    }
  }

  const { data, error } = await req.supabase
    .from('users')
    .insert({ email, display_name })
    .select('id, email, display_name, api_key')
    .single();

  if (error) {
    if (error.code === '23505') {
      return res.status(409).json({ error: 'Email already registered' });
    }
    return res.status(500).json({ error: error.message });
  }

  res.status(201).json({
    user: { id: data.id, email: data.email, display_name: data.display_name },
    api_key: data.api_key,
    message: 'Store this API key securely. Set it as MARKETING_CLOUD_API_KEY env var.'
  });
});

// GET /api/auth/me
router.get('/me', authMiddleware, async (req, res) => {
  res.json({ user: req.user });
});

// POST /api/auth/rotate-key
router.post('/rotate-key', authMiddleware, async (req, res) => {
  const newKey = crypto.randomBytes(32).toString('hex');

  const { error } = await req.supabase
    .from('users')
    .update({ api_key: newKey })
    .eq('id', req.user.id);

  if (error) {
    return res.status(500).json({ error: error.message });
  }

  res.json({ api_key: newKey });
});

module.exports = router;
