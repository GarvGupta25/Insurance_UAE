import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { MapPin, Navigation } from 'lucide-react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { api } from './api';

export function Providers({ planId }: { planId: string }) {
  const [emirate, setEmirate] = useState('Dubai'); const [location, setLocation] = useState<{ lat: number; lng: number } | null>(null); const [error, setError] = useState('');
  const mapRoot = useRef<HTMLDivElement>(null); const [showMap, setShowMap] = useState(false);
  const { data } = useQuery({ queryKey: ['providers', planId, emirate], queryFn: () => api(`/api/providers?plan_id=${encodeURIComponent(planId)}&emirate=${encodeURIComponent(emirate)}`) });
  useEffect(() => {
    if (!showMap || !mapRoot.current || !data?.items.length) return;
    const first = data.items[0]; const map = L.map(mapRoot.current, { scrollWheelZoom: false }).setView([first.lat, first.lng], 12);
    // Network tiles are requested only after the user opens the map; the list is fully usable without them.
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' }).addTo(map);
    for (const item of data.items) { const label = document.createElement('span'); label.textContent = `${item.name} — fictional facility`; L.circleMarker([item.lat, item.lng], { radius: 8, color: '#315aa5', fillOpacity: 0.8 }).addTo(map).bindPopup(label); }
    return () => { map.remove(); };
  }, [data, showMap]);
  function locate() {
    setError(''); if (!navigator.geolocation) { setError('Location is unavailable. Choose an emirate below.'); return; }
    navigator.geolocation.getCurrentPosition(pos => setLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude }), () => setError('Location was unavailable or declined. The emirate list still works.'), { timeout: 10000, maximumAge: 60000 });
  }
  function distance(p: any) {
    if (!location) return 0; const r = Math.PI / 180; const dlat = (p.lat - location.lat) * r; const dlng = (p.lng - location.lng) * r;
    return 6371 * 2 * Math.atan2(Math.sqrt(Math.sin(dlat / 2) ** 2 + Math.cos(location.lat * r) * Math.cos(p.lat * r) * Math.sin(dlng / 2) ** 2), Math.sqrt(1 - (Math.sin(dlat / 2) ** 2 + Math.cos(location.lat * r) * Math.cos(p.lat * r) * Math.sin(dlng / 2) ** 2)));
  }
  return <section className="surface"><div className="section-heading"><div><h2>Care, in context.</h2><p className="muted">A fictional network directory to demonstrate the experience.</p></div><button className="secondary" onClick={locate}><Navigation size={16}/> Use my location</button></div><label className="field narrow">Emirate<select value={emirate} onChange={e => { setEmirate(e.target.value); setShowMap(false); }}>{['Dubai', 'Abu Dhabi', 'Sharjah', 'Ajman', 'Fujairah', 'Ras Al Khaimah', 'Umm Al Quwain'].map(e => <option key={e}>{e}</option>)}</select></label>
    <p className="notice">{data?.notice}</p>{error && <p className="error" role="alert">{error}</p>}{data?.items.length ? <><button className="quiet" onClick={() => setShowMap(!showMap)}>{showMap ? 'Hide map' : 'Show map (loads OpenStreetMap)'}</button>{showMap && <div ref={mapRoot} className="provider-map" aria-label="Map of fictional provider locations"/>}{[...data.items].sort((a, b) => distance(a) - distance(b)).map(item => <div className="list-row" key={item.id}><span className="list-icon"><MapPin size={21}/></span><div><strong>{item.name}</strong><small>{item.tier.replaceAll('_', ' ')} · {item.source}{location ? ` · approximately ${distance(item).toFixed(1)} km straight-line distance` : ''}</small></div><span className="badge neutral">Demo network</span></div>)}</> : <p>No fictional providers are seeded for this emirate. No real network match is implied.</p>}
    <small className="muted">Your precise location stays in this page's memory and is not saved to your profile. Nearby does not imply real coverage or availability.</small></section>;
}
