import { Link } from 'react-router-dom';
import { Compass } from 'lucide-react';

const SITE_LINKS = [
  { heading: 'Explore', links: [
    { to: '/', label: 'Home' },
    { to: '/plans', label: 'Popular Schemes' },
    { to: '/how-it-works', label: 'How It Works' },
    { to: '/guide', label: 'New to the UAE?' },
  ]},
  { heading: 'Company', links: [
    { to: '/about', label: 'About' },
    { to: '/partners', label: 'Partners' },
    { to: '/faq', label: 'FAQ' },
    { to: '/contact', label: 'Contact' },
    { to: '/claims-explained', label: 'Claims & Support' },
  ]},
  { heading: 'Legal', links: [
    { to: '/legal/privacy', label: 'Privacy Policy' },
    { to: '/legal/terms', label: 'Terms of Use' },
    { to: '/legal/disclaimer', label: 'Disclaimer' },
  ]},
];

export function MarketingFooter() {
  return (
    <footer className="mf-footer">
      <div className="mf-footer__inner m-page-shell">
        {/* Brand + tagline */}
        <div className="mf-footer__brand">
          <Link to="/" className="brand" aria-label="Helm AI home">
            <span><Compass size={25} /></span>
            helm<span className="brand-ai">ai</span>
          </Link>
          <p className="mf-footer__tagline">Clarity at every step.</p>
        </div>

        {/* Site map */}
        <div className="mf-footer__links">
          {SITE_LINKS.map(group => (
            <div key={group.heading} className="mf-footer__group">
              <span className="mf-footer__group-heading">{group.heading}</span>
              {group.links.map(link => (
                <Link key={link.to} to={link.to} className="mf-footer__link">
                  {link.label}
                </Link>
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* Disclaimer bar */}
      <div className="mf-footer__disclaimer">
        <p>
          Helm AI is a demonstration product. Plans, pricing, and partner names
          shown are fictional and for illustration only.
        </p>
        <span>© {new Date().getFullYear()} Helm AI · Synthetic demonstration</span>
      </div>
    </footer>
  );
}
