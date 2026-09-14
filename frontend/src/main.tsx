import React, { useEffect, useState } from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route, Link, NavLink, Navigate, Outlet, useNavigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import type { Session } from '@supabase/supabase-js';
import { Compass, ArrowUpRight, ArrowRight, Mic, ShieldCheck, Layers3, LayoutDashboard, LogOut, Menu, Check, Sparkles, ClipboardCheck } from 'lucide-react';
import { api, auth, configureAuth, type Config, aed } from './api';
import { Dashboard, Intake, QuotePage, ApplicationPage, PolicyPage, Loading, ErrorView } from './Shopping';
import { BrokerWorkspace } from './Broker';
import './styles.css';

const client = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } });
const localPreview = import.meta.env.VITE_LOCAL_PREVIEW === '1';
function previewSession(): Session | null {
  if (!localPreview) return null;
  const broker = sessionStorage.getItem('helm-preview-role') === 'broker';
  return { user: { id: broker ? '10000000-0000-4000-8000-000000000002' : '10000000-0000-4000-8000-000000000001',
    email: broker ? 'demo-broker@helm.local' : 'demo-member@helm.local' } } as Session;
}

function Brand() { return <Link to="/" className="brand" aria-label="Helm AI home"><span><Compass size={25}/></span>helm<span className="brand-ai">ai</span></Link>; }
function Landing() {
  const catalogue = useQuery({ queryKey: ['catalogue'], queryFn: () => api('/api/catalogue') });
  return <div className="landing"><header className="public-nav"><Brand/><nav aria-label="Main navigation"><a href="#how-it-works">How it works</a><a href="#plans">Explore plans</a><a href="#questions">Questions</a></nav><Link className="button secondary" to="/login">Your workspace <ArrowUpRight size={16}/></Link></header>
    <main><section className="hero"><div className="hero-copy"><span className="eyebrow"><span className="small-dot"/> HEALTH INSURANCE. HUMAN AGAIN.</span><h1>Cover choices.<br/><span>Clear answers.</span></h1><p>Health cover should make you feel more certain.<br className="desktop-break"/> Tell us what matters. We’ll help you understand your options, one conversation at a time.</p><div className="hero-actions"><Link className="button" to="/login">Find my cover <ArrowRight size={19}/></Link><Link className="text-link" to="/login"><Mic size={18}/> Try voice intake</Link></div><div className="hero-footnotes"><span><Check size={15}/> Speak or type</span><span><Check size={15}/> Understand the tradeoffs</span></div></div>
    <div className="hero-product"><div className="preview-top"><span className="assistant-avatar"><Sparkles size={20}/></span><div><strong>A little more you.<br/>A lot less paperwork.</strong></div><span className="badge neutral">Sample journey</span></div><div className="preview-question">“I’m looking for good hospital access, without paying for benefits I won’t use.”</div><div className="preview-answer"><span className="eyebrow">START WITH WHAT MATTERS</span><h2>Let’s look at<br/>the whole picture.</h2><ul><li><span>01</span> Your health and upcoming care</li><li><span>02</span> Where and when you need cover</li><li><span>03</span> Your budget and priorities</li></ul></div><div className="preview-footer"><span><ShieldCheck size={19}/> Your details, connected</span><span className="voice-orb"><Mic size={23}/></span></div></div></section>
    <div className="demo-strip"><ShieldCheck size={18}/><span>A working product demonstration using fictional plans and people. No real cover is sold.</span></div>
    <section id="how-it-works" className="landing-section"><div className="section-heading"><div><span className="eyebrow">LESS BACK-AND-FORTH. MORE UNDERSTANDING.</span><h2>From your first question<br/>to your next step.</h2></div><p>You shouldn’t have to start over<br/>every time you need an answer.</p></div><div className="steps"><article><span className="step-number">01</span><Mic/><h3>Tell us your story.</h3><p>Speak naturally or type. Review the details as your reusable insurance profile takes shape.</p></article><article><span className="step-number">02</span><Layers3/><h3>See the real tradeoffs.</h3><p>Compare premiums, waiting periods and network access against the needs you’ve shared.</p></article><article><span className="step-number">03</span><ShieldCheck/><h3>Keep your cover close.</h3><p>Review your application, try sandbox payments and find your saved policy details in one place.</p></article></div></section>
    <section id="plans" className="landing-section plan-preview"><span className="eyebrow">A SMALL CATALOGUE. MEANINGFUL DIFFERENCES.</span><h2>More cover isn’t always a better fit.</h2><p>Explore the three fictional plans used in this demonstration.</p><div className="sample-plans">{catalogue.data?.plans.map((p: any) => <article key={p.id}><span className="eyebrow">{p.network.toUpperCase()} NETWORK</span><h3>{p.name}</h3><strong>{aed(p.annual_premium * 100)}<small> / year</small></strong><p>{p.network_note}</p><Link className="text-link" to="/login">Compare for my needs <ArrowRight size={16}/></Link></article>)}</div>{catalogue.error && <p>The sample catalogue is temporarily unavailable.</p>}</section>
    <section id="questions" className="landing-section faq"><div><span className="eyebrow">A FEW THINGS, MADE CLEAR.</span><h2>Good questions.<br/>Straight answers.</h2></div><div>{[['Is this real insurance?', 'This is a synthetic demonstration. Quotes, carriers, providers, applications and local payment schedules are fictional. No real insurance cover is issued.'], ['Can I speak instead of filling a form?', 'Yes, when voice is configured. Record a short answer, review the transcript and check the details before saving. Typing and an editable profile remain available.'], ['Does a covered benefit work immediately?', 'Not necessarily. A benefit can have a waiting period, network restriction or limit. Helm shows those conditions alongside the price.'], ['Does a test payment mean I am covered?', 'No. A local simulation or test-provider receipt cannot activate real insurance.'], ['Can I change my answers?', 'Yes. Saved corrections update your profile and make affected old quotes stale. The terms saved with an existing policy remain unchanged.']].map(([question, answer]) => <details key={question}><summary>{question}</summary><p>{answer}</p></details>)}</div></section>
    <section className="closing"><div><span className="eyebrow">YOUR NEXT STEP CAN BE A SIMPLE ONE.</span><h2>Start with a conversation.</h2></div><Link className="button light-button" to="/login">Meet your cover options <ArrowRight size={18}/></Link></section></main>
    <footer className="public-footer"><Brand/><p>Clarity at every step.</p><span>Helm AI · Synthetic demonstration</span></footer></div>;
}

function Login({ session, config }: { session: Session | null; config: Config }) {
  const [mode, setMode] = useState<'login' | 'signup' | 'recover' | 'reset'>('login'); const [message, setMessage] = useState(''); const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  useEffect(() => { if (new URLSearchParams(location.search).has('recovery')) setMode('reset'); }, []);
  if (session && mode !== 'reset' && !new URLSearchParams(location.search).has('recovery')) return <Navigate to="/app" replace/>;
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!auth) return; setBusy(true); setMessage(''); const values = new FormData(event.currentTarget);
    const email = String(values.get('email') || ''); const password = String(values.get('password') || '');
    try {
      if (mode === 'recover') { const { error } = await auth.auth.resetPasswordForEmail(email, { redirectTo: location.origin + '/login?recovery=1' }); if (error) throw error; setMessage('If this account exists, a recovery link has been sent.'); }
      else if (mode === 'reset') { const { error } = await auth.auth.updateUser({ password }); if (error) throw error; navigate('/app'); }
      else if (mode === 'signup') { const { data, error } = await auth.auth.signUp({ email, password, options: { emailRedirectTo: location.origin + '/app' } }); if (error) throw error; if (!data.session) setMessage('Check your email to verify your account, then sign in.'); else navigate('/app'); }
      else { const { error } = await auth.auth.signInWithPassword({ email, password }); if (error) throw error; navigate('/app'); }
    } catch (e) { setMessage((e as Error).message); } finally { setBusy(false); }
  }
  return <div className="auth-page"><div className="auth-story"><Brand/><span className="eyebrow">A CLEARER WAY TO FIND COVER</span><h1>Your needs.<br/>Your choices.<br/><span>All connected.</span></h1><p>A little understanding goes a long way.<br/>Let’s find where your cover should start.</p><span className="badge light">Fictional insurance demonstration</span></div><main className="auth-panel"><Link className="text-link" to="/">← Back to Helm</Link><div className="auth-form"><span className="eyebrow">WELCOME TO HELM</span><h2>{mode === 'signup' ? 'Make yourself at home.' : mode === 'recover' ? 'Find your way back.' : mode === 'reset' ? 'Choose a new password.' : 'Good to see you.'}</h2><p>{mode === 'login' ? 'Sign in to pick up where you left off.' : 'Your profile will be saved with your account.'}</p>
    {!config.auth_configured && <div className="notice">Account access is not configured yet. Connect local or hosted Supabase to enable sign-in and saved profiles.</div>}
    <form onSubmit={submit}>{mode !== 'reset' && <label className="field">Email address<input name="email" type="email" autoComplete="email" required placeholder="you@example.com"/></label>}{mode !== 'recover' && <label className="field">Password<input name="password" type="password" minLength={8} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required placeholder="At least 8 characters"/></label>}<button disabled={busy || !config.auth_configured}>{busy ? 'Please wait…' : mode === 'signup' ? 'Create account' : mode === 'recover' ? 'Send recovery link' : mode === 'reset' ? 'Update password' : 'Sign in'}<ArrowRight size={17}/></button></form>
    {message && <p className="notice" role="status">{message}</p>}<div className="auth-links"><button className="quiet" onClick={() => { setMessage(''); setMode(mode === 'signup' ? 'login' : 'signup'); }}>{mode === 'signup' ? 'Already have an account? Sign in' : 'New here? Create an account'}</button><button className="quiet" onClick={() => { setMessage(''); setMode('recover'); }}>Forgot password?</button></div><small>Passwords stay in the sign-in flow. Never share passwords, card details or one-time codes with the assistant.</small></div></main></div>;
}

function Shell({ session }: { session: Session | null }) {
  const [open, setOpen] = useState(false); const navigate = useNavigate();
  const access = useQuery({ queryKey: ['access', session?.user.id], queryFn: () => api<{ role: 'member' | 'broker' }>('/api/me/access'), enabled: !!session });
  if (!session) return <Navigate to="/login" replace/>;
  async function logout() { if ('speechSynthesis' in window) window.speechSynthesis.cancel(); if (localPreview) { sessionStorage.setItem('helm-preview-role', 'member'); window.location.assign('/'); return; } await auth?.auth.signOut(); client.clear(); navigate('/'); }
  function switchPreviewRole() { sessionStorage.setItem('helm-preview-role', access.data?.role === 'broker' ? 'member' : 'broker'); window.location.assign(access.data?.role === 'broker' ? '/app' : '/app/broker'); }
  return <div className="app-shell"><a className="skip-link" href="#workspace">Skip to workspace</a><aside className={`sidebar ${open ? 'open' : ''}`}><Brand/><span className="nav-caption">YOUR WORKSPACE</span><nav><NavLink end to="/app" onClick={() => setOpen(false)}><LayoutDashboard size={19}/> Overview</NavLink><Link to="/app" onClick={() => setOpen(false)}><ShieldCheck size={19}/> Policies & cover</Link>{access.data?.role === "broker" && <NavLink to="/app/broker" onClick={() => setOpen(false)}><ClipboardCheck size={19}/> Broker workspace</NavLink>}<Link to="/#questions"><MessageIcon/> About this demo</Link></nav><div className="sidebar-bottom"><div className="sidebar-note"><ShieldCheck size={22}/><strong>Clarity, not guesswork.</strong><p>Your choices stay yours. Review the details before every submission.</p></div>{localPreview && <button className="quiet" onClick={switchPreviewRole}><ClipboardCheck size={17}/> Switch to {access.data?.role === 'broker' ? 'member' : 'broker'} demo</button>}<button className="quiet" onClick={logout}><LogOut size={17}/> {localPreview ? 'Back to start' : 'Sign out'}</button></div></aside><div className="app-content"><header className="workspace-header"><button className="mobile-menu quiet" onClick={() => setOpen(!open)} aria-label="Toggle navigation" aria-expanded={open}><Menu size={23}/></button><span>Individual health insurance <span className="header-divider">/</span> UAE</span><div><span className="badge neutral">{localPreview ? 'Local synthetic preview' : 'Demo workspace'}</span><span className="user-avatar" title={session.user.email}>{session.user.email?.[0]?.toUpperCase() || 'H'}</span></div></header><main id="workspace"><Outlet/></main><footer className="workspace-footer">Helm AI · All insurance products and transactions in this workspace are demonstrations.</footer></div></div>;
}
function MessageIcon() { return <Layers3 size={19}/>; }
function App() {
  const config = useQuery({ queryKey: ['config'], queryFn: () => api<Config>('/api/config') }); const [session, setSession] = useState<Session | null>(previewSession); const [ready, setReady] = useState(false);
  useEffect(() => {
    if (!config.data) return; configureAuth(config.data);
    if (!auth) { setReady(true); return; }
    let active = true; void auth.auth.getSession().then(({ data }) => { if (active) { setSession(data.session); setReady(true); } });
    const { data: subscription } = auth.auth.onAuthStateChange((_event, next) => { setSession(next); setReady(true); });
    return () => { active = false; subscription.subscription.unsubscribe(); };
  }, [config.data]);
  if (config.error) return <div className="startup-error"><Brand/><h1>The workspace service is unavailable.</h1><p>Start the Helm API, then reload this page.</p><ErrorView error={config.error}/><button onClick={() => { void config.refetch(); }}>Try again</button></div>;
  if (!config.data || !ready) return <Loading/>;
  return <Routes><Route path="/" element={<Landing/>}/><Route path="/login" element={<Login session={session} config={config.data}/>}/><Route path="/app" element={<Shell session={session}/>}><Route index element={<Dashboard/>}/><Route path="intake/:caseId" element={<Intake config={config.data}/>}/><Route path="quotes/:quoteId" element={<QuotePage/>}/><Route path="applications/:applicationId" element={<ApplicationPage/>}/><Route path="broker" element={<BrokerWorkspace/>}/><Route path="policies/:policyId" element={<PolicyPage config={config.data}/>}/></Route><Route path="*" element={<Navigate to="/" replace/>}/></Routes>;
}
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><QueryClientProvider client={client}><BrowserRouter><App/></BrowserRouter></QueryClientProvider></React.StrictMode>);
