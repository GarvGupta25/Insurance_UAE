import { useState, useRef } from 'react';
import { PageShell, Section, SurfaceCard } from '../components';
import './ContactPage.css';

export function ContactPage() {
  const [errors, setErrors] = useState<{ field: string; message: string; id: string }[]>([]);
  const errorSummaryRef = useRef<HTMLDivElement>(null);

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    
    const formData = new FormData(e.currentTarget);
    const name = formData.get('name') as string;
    const email = formData.get('email') as string;
    const message = formData.get('message') as string;

    const newErrors = [];
    if (!name.trim()) newErrors.push({ field: 'name', message: 'Name is required.', id: 'contact-name' });
    if (!email.trim()) newErrors.push({ field: 'email', message: 'Email is required.', id: 'contact-email' });
    if (!message.trim()) newErrors.push({ field: 'message', message: 'Message cannot be empty.', id: 'contact-message' });

    if (newErrors.length > 0) {
      setErrors(newErrors);
      // Move focus to error summary
      setTimeout(() => errorSummaryRef.current?.focus(), 0);
    } else {
      setErrors([]);
      // Intentionally no-op for demonstration
      e.currentTarget.reset();
      alert("Message sent (demo).");
    }
  };

  const getFieldError = (field: string) => errors.find((e) => e.field === field);

  return (
    <PageShell>
      <Section id="contact-hero">
        <div className="contact-hero">
          <h1>Contact Us</h1>
          <p>Have questions about how the platform works? Get in touch.</p>
        </div>
      </Section>

      <Section id="contact-form-section" tinted>
        <SurfaceCard className="contact-card">
          <form className="contact-form" onSubmit={handleSubmit} noValidate>
            
            {errors.length > 0 && (
              <div 
                className="form-error-summary" 
                role="alert" 
                tabIndex={-1} 
                ref={errorSummaryRef}
              >
                <h3>Please fix the following errors:</h3>
                <ul>
                  {errors.map((error, idx) => (
                    <li key={idx}>
                      <a href={`#${error.id}`}>{error.message}</a>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="contact-form-group">
              <label htmlFor="contact-name">Name</label>
              <input 
                type="text" 
                id="contact-name" 
                name="name" 
                placeholder="Jane Doe" 
                aria-invalid={!!getFieldError('name')}
                aria-describedby={getFieldError('name') ? "contact-name-error" : undefined}
              />
              {getFieldError('name') && (
                <span id="contact-name-error" className="field-error" role="alert">
                  {getFieldError('name')?.message}
                </span>
              )}
            </div>

            <div className="contact-form-group">
              <label htmlFor="contact-email">Email</label>
              <input 
                type="email" 
                id="contact-email" 
                name="email" 
                placeholder="jane@example.com" 
                aria-invalid={!!getFieldError('email')}
                aria-describedby={getFieldError('email') ? "contact-email-error" : undefined}
              />
              {getFieldError('email') && (
                <span id="contact-email-error" className="field-error" role="alert">
                  {getFieldError('email')?.message}
                </span>
              )}
            </div>

            <div className="contact-form-group">
              <label htmlFor="contact-message">Message</label>
              <textarea 
                id="contact-message" 
                name="message" 
                rows={5} 
                placeholder="How can we help?"
                aria-invalid={!!getFieldError('message')}
                aria-describedby={getFieldError('message') ? "contact-message-error" : undefined}
              ></textarea>
              {getFieldError('message') && (
                <span id="contact-message-error" className="field-error" role="alert">
                  {getFieldError('message')?.message}
                </span>
              )}
            </div>

            <div className="contact-form-actions">
              <button type="reset" className="m-button-secondary" onClick={() => setErrors([])}>Clear</button>
              <button type="submit" className="m-button-primary">Send Message</button>
            </div>
          </form>
          
          <div className="contact-demo-notice">
            <strong>This is a demo product.</strong> Messages sent here are not monitored and will not reach a real support team.
          </div>
        </SurfaceCard>
      </Section>
    </PageShell>
  );
}
