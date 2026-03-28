const { Router } = require('express');
const { authMiddleware, teamMemberMiddleware } = require('../middleware/auth');
const router = Router();

router.use(authMiddleware);

// POST /api/teams
router.post('/', async (req, res) => {
  const { name, slug } = req.body;
  if (!name) return res.status(400).json({ error: 'name required' });

  const teamSlug = slug || name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');

  const { data: team, error } = await req.supabase
    .from('teams')
    .insert({ name, slug: teamSlug, created_by: req.user.id })
    .select()
    .single();

  if (error) {
    if (error.code === '23505') {
      return res.status(409).json({ error: 'Team slug already exists' });
    }
    return res.status(500).json({ error: error.message });
  }

  const { error: memberError } = await req.supabase.from('team_members').insert({
    team_id: team.id,
    user_id: req.user.id,
    role: 'owner'
  });

  if (memberError) {
    // Rollback: delete the team since owner could not be added
    await req.supabase.from('teams').delete().eq('id', team.id);
    return res.status(500).json({ error: 'Failed to set team owner' });
  }

  res.status(201).json({ team });
});

// GET /api/teams
router.get('/', async (req, res) => {
  const { data: memberships, error } = await req.supabase
    .from('team_members')
    .select('team_id, role, teams(id, name, slug, created_at)')
    .eq('user_id', req.user.id);

  if (error) return res.status(500).json({ error: error.message });

  const teams = memberships.map(m => ({
    ...m.teams,
    role: m.role
  }));

  res.json({ teams });
});

// GET /api/teams/:teamId/members
router.get('/:teamId/members', teamMemberMiddleware, async (req, res) => {
  const { data, error } = await req.supabase
    .from('team_members')
    .select('role, joined_at, users(id, email, display_name)')
    .eq('team_id', req.params.teamId);

  if (error) return res.status(500).json({ error: error.message });

  res.json({
    members: data.map(m => ({ ...m.users, role: m.role, joined_at: m.joined_at }))
  });
});

// POST /api/teams/:teamId/invite
router.post('/:teamId/invite', teamMemberMiddleware, async (req, res) => {
  if (!['owner', 'admin'].includes(req.teamRole)) {
    return res.status(403).json({ error: 'Only owners and admins can invite' });
  }

  const { email, role } = req.body;
  if (!email) return res.status(400).json({ error: 'email required' });

  const inviteRole = role || 'member';
  if (!['member', 'viewer', 'admin'].includes(inviteRole)) {
    return res.status(400).json({ error: 'Invalid role. Must be member, viewer, or admin' });
  }

  const { data: invitation, error } = await req.supabase
    .from('invitations')
    .insert({
      team_id: req.params.teamId,
      invited_by: req.user.id,
      email,
      role: inviteRole
    })
    .select()
    .single();

  if (error) return res.status(500).json({ error: error.message });

  res.status(201).json({
    invitation: { id: invitation.id, token: invitation.token },
    join_command: `/marketing teams join ${invitation.token}`
  });
});

// POST /api/teams/join
router.post('/join', async (req, res) => {
  const { token } = req.body;
  if (!token) return res.status(400).json({ error: 'token required' });

  // Atomically claim the invite (H4: race condition fix)
  const { data: invite, error } = await req.supabase
    .from('invitations')
    .update({ status: 'accepted' })
    .eq('token', token)
    .eq('status', 'pending')
    .gt('expires_at', new Date().toISOString())
    .select('*')
    .single();

  if (error || !invite) {
    return res.status(404).json({ error: 'Invalid or expired invitation' });
  }

  // H5: verify the invite was intended for this user's email
  if (invite.email !== req.user.email) {
    // Revert the invite status since it's not for this user
    await req.supabase
      .from('invitations')
      .update({ status: 'pending' })
      .eq('id', invite.id);
    return res.status(403).json({ error: 'This invitation was sent to a different email address' });
  }

  const { error: memberError } = await req.supabase
    .from('team_members')
    .insert({
      team_id: invite.team_id,
      user_id: req.user.id,
      role: invite.role
    });

  if (memberError) {
    // Revert invite status on failure
    await req.supabase
      .from('invitations')
      .update({ status: 'pending' })
      .eq('id', invite.id);
    if (memberError.code === '23505') {
      return res.status(409).json({ error: 'Already a member of this team' });
    }
    return res.status(500).json({ error: memberError.message });
  }

  res.json({ message: 'Joined team successfully', team_id: invite.team_id });
});

// DELETE /api/teams/:teamId/members/:userId
router.delete('/:teamId/members/:userId', teamMemberMiddleware, async (req, res) => {
  if (!['owner', 'admin'].includes(req.teamRole)) {
    return res.status(403).json({ error: 'Only owners and admins can remove members' });
  }

  const targetUserId = req.params.userId;

  // Prevent removing the owner
  const { data: target } = await req.supabase
    .from('team_members')
    .select('role')
    .eq('team_id', req.params.teamId)
    .eq('user_id', targetUserId)
    .single();

  if (!target) {
    return res.status(404).json({ error: 'Member not found' });
  }
  if (target.role === 'owner') {
    return res.status(403).json({ error: 'Cannot remove team owner' });
  }
  // Admins cannot remove other admins
  if (req.teamRole === 'admin' && target.role === 'admin') {
    return res.status(403).json({ error: 'Admins cannot remove other admins' });
  }

  const { error } = await req.supabase
    .from('team_members')
    .delete()
    .eq('team_id', req.params.teamId)
    .eq('user_id', targetUserId);

  if (error) return res.status(500).json({ error: error.message });

  res.json({ message: 'Member removed' });
});

module.exports = router;
