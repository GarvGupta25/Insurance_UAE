import { useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { MarketingHeader } from './MarketingHeader';
import { MarketingFooter } from './MarketingFooter';
import { ChatbotLauncher } from './ChatbotLauncher';
import '../tokens.css';
import '../marketing.css';
import './MarketingLayout.css';
export function MarketingLayout() {
  useEffect(() => { const observer = new IntersectionObserver((entries) => { entries.forEach((entry) => { if (entry.isIntersecting) { entry.target.classList.add('is-visible'); observer.unobserve(entry.target); } }); }, { rootMargin: '0px 0px -50px 0px', threshold: 0.1 }); const elements = document.querySelectorAll('.scroll-reveal'); elements.forEach((el) => observer.observe(el)); return () => observer.disconnect(); }, []);
  return <div className="marketing-layout"><MarketingHeader /><main className="marketing-layout__main"><Outlet /></main><MarketingFooter /><ChatbotLauncher /></div>;
}
