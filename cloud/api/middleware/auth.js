async function authMiddleware(req, res, next) {
  const apiKey = req.headers['x-api-key'];
  if (!apiKey) {
    return res.status(401).json({ error: 'Missing x-api-key header' });
  }

  const { data: user, error } = await req.supabase
    .from('users')
    .select('id, email, display_name')
    .eq('api_key', apiKey)
    .single();

  if (error || !user) {
    return res.status(401).json({ error: 'Invalid API key' });
  }

  req.user = user;
  next();
}

async function teamMemberMiddleware(req, res, next) {
  const teamId = req.params.teamId || req.body.team_id;
  if (!teamId) {
    return res.status(400).json({ error: 'team_id required' });
  }

  const { data: membership, error } = await req.supabase
    .from('team_members')
    .select('role')
    .eq('team_id', teamId)
    .eq('user_id', req.user.id)
    .single();

  if (error || !membership) {
    return res.status(403).json({ error: 'Not a member of this team' });
  }

  req.teamRole = membership.role;
  next();
}

module.exports = { authMiddleware, teamMemberMiddleware };
