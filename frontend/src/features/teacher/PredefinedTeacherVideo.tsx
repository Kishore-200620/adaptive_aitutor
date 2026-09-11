import { useEffect, useRef, useState } from 'react';

interface PredefinedTeacherVideoProps {
  url: string;
  onEnded: () => void;
}

export function PredefinedTeacherVideo({ url, onEnded }: PredefinedTeacherVideoProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [opacity, setOpacity] = useState(0);

  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.play().catch(e => console.error("[EDUVA][PredefinedVideo] Playback failed:", e));
    }
    // Small delay to ensure CSS transition triggers on mount
    const timer = setTimeout(() => setOpacity(1), 50);
    return () => clearTimeout(timer);
  }, [url]);

  const handleEnded = () => {
    setOpacity(0);
    setTimeout(onEnded, 300); // Wait for fade out before notifying parent to unmount
  };

  return (
    <div style={{
      width: '100%',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      marginBottom: '1rem',
      position: 'relative',
      opacity: opacity,
      transition: 'opacity 300ms ease-in-out'
    }}>
      <div style={{
        width: '100%',
        maxWidth: '400px',
        aspectRatio: '1 / 1',
        backgroundColor: '#e2e8f0',
        borderRadius: 'var(--radius-lg)',
        overflow: 'hidden',
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
      }}>
        <video 
          ref={videoRef} 
          src={url}
          onEnded={handleEnded}
          autoPlay 
          playsInline
          muted // Muted to preserve Edge TTS as the single audio owner
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
        />
      </div>
    </div>
  );
}
