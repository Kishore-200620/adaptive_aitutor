import type { PresentationDecision } from '../../types/api'
import { eduvaApi } from '../../lib/api'
import { LiveAiTeacher } from './LiveAiTeacher'
import { PredefinedTeacherVideo } from './PredefinedTeacherVideo'
import { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import remarkGfm from 'remark-gfm';
import 'katex/dist/katex.min.css';

import type { PresentationUnit } from '../../lib/api'

// Helper to replace LaTeX delimiters with standard Markdown math delimiters
function formatMathDelimiters(text: string): string {
  if (!text) return text;
  return text
    .replace(/\\\[/g, '$$$$')
    .replace(/\\\]/g, '$$$$')
    .replace(/\\\(/g, '$')
    .replace(/\\\)/g, '$');
}

interface AiTeacherWorkspaceProps {
  teachingText: string;
  presentation: PresentationDecision | null;
  audioUrl: string | null;
  presentationUnits?: PresentationUnit[];
  audioEnabled: boolean;
  isStreaming: boolean;
}

export function AiTeacherWorkspace({ teachingText, presentation, audioUrl, presentationUnits, audioEnabled, isStreaming }: AiTeacherWorkspaceProps) {
  const [audioOwner, setAudioOwner] = useState<'simli' | 'fallback' | 'none'>('fallback');
  const [videoCompleted, setVideoCompleted] = useState(false);
  const [playableAudioUrl, setPlayableAudioUrl] = useState<string | null>(null);
  const fallbackAudioRef = useRef<HTMLAudioElement>(null);
  const currentClipIdRef = useRef<string | null>(null);

  const [currentUnitIndex, setCurrentUnitIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);

  // If presentationUnits changes heavily (e.g. cleared), reset index
  useEffect(() => {
    if (!presentationUnits || presentationUnits.length === 0) {
      setCurrentUnitIndex(0);
      setIsPlaying(false);
    }
  }, [presentationUnits]);

  const currentAudioUrl = presentationUnits && presentationUnits.length > currentUnitIndex 
    ? presentationUnits[currentUnitIndex].audio_url 
    : audioUrl;

  const handleAudioEnded = useCallback(() => {
    setIsPlaying(false);
    if (presentationUnits && currentUnitIndex < presentationUnits.length - 1) {
      setCurrentUnitIndex(prev => prev + 1);
    } else if (presentationUnits && presentationUnits.length > 0 && currentUnitIndex === presentationUnits.length - 1) {
      // Reached the end of the queue, but more chunks might arrive.
      setCurrentUnitIndex(prev => prev + 1);
    }
  }, [presentationUnits, currentUnitIndex]);

  // Poll for audio readiness
  useEffect(() => {
    if (!currentAudioUrl) {
      setPlayableAudioUrl(null);
      return;
    }

    let isMounted = true;
    let pollInterval: number | null = null;

    const checkAudio = async () => {
      try {
        const statusUrl = currentAudioUrl.replace('/audio/', '/audio/status/');
        const response = await eduvaApi.checkAudioStatus(statusUrl);
        
        if (!isMounted) return;

        if (response.status === 'ready') {
          setPlayableAudioUrl(currentAudioUrl);
          if (pollInterval) clearInterval(pollInterval);
        } else if (response.status === 'failed') {
          setPlayableAudioUrl(null);
          if (pollInterval) clearInterval(pollInterval);
        }
      } catch (err) {
        // network error, continue polling
      }
    };

    checkAudio();
    pollInterval = setInterval(checkAudio, 2000);

    return () => {
      isMounted = false;
      if (pollInterval) clearInterval(pollInterval);
    };
  }, [currentAudioUrl]);

  // Reset videoCompleted when a new clip_id arrives
  useEffect(() => {
    if (presentation?.teacher_video?.clip_id && presentation.teacher_video.clip_id !== currentClipIdRef.current) {
      setVideoCompleted(false);
      currentClipIdRef.current = presentation.teacher_video.clip_id;
    }
  }, [presentation?.teacher_video?.clip_id]);

  // Handle native fallback audio when audioOwner is 'fallback'
  useEffect(() => {
    const audio = fallbackAudioRef.current;
    if (!audio) return;

    const handleCanPlay = () => {
      if (audioOwner === 'fallback' && audioEnabled) {
        audio.play().catch(e => console.error("Fallback audio play failed", e));
      }
    };
    
    const handlePlay = () => {
      setIsPlaying(true);
    };

    audio.addEventListener('canplay', handleCanPlay);
    audio.addEventListener('play', handlePlay);
    audio.addEventListener('ended', handleAudioEnded);
    return () => {
      audio.removeEventListener('canplay', handleCanPlay);
      audio.removeEventListener('play', handlePlay);
      audio.removeEventListener('ended', handleAudioEnded);
    };
  }, [audioOwner, audioEnabled, handleAudioEnded]);

  useEffect(() => {
    const audio = fallbackAudioRef.current;
    if (!audio) return;

    if (audioOwner === 'fallback' && playableAudioUrl && audioEnabled) {
      const fullAudioUrl = `${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}${playableAudioUrl}`;
      if (audio.src !== fullAudioUrl) {
        audio.src = fullAudioUrl;
        // play() will be triggered by handleCanPlay when ready
      } else if (audio.paused) {
        audio.play().catch(e => console.error("Fallback audio play failed", e));
      }
    } else if (audioOwner !== 'fallback' || !audioEnabled) {
      audio.pause();
    }
  }, [audioOwner, playableAudioUrl, audioEnabled]);

  const parsedStream = useMemo(() => {
    let narration = "";
    let blackboard = "";
    
    // Robust extraction ignoring order, allowing optional markdown asterisks
    const bbMatch = teachingText.match(/\*?\*?BLACKBOARD:\*?\*?\s*([\s\S]*?)(?:(?:\n\*?\*?VISUAL_DIRECTIVE:\*?\*?)|(?:\n\*?\*?NARRATION:\*?\*?)|(?:\n\*?\*?QUESTION:\*?\*?)|$)/);
    if (bbMatch) {
      blackboard = bbMatch[1].trim();
    }
    
    const narrMatch = teachingText.match(/\*?\*?NARRATION:\*?\*?\s*([\s\S]*?)(?:(?:\n\*?\*?BLACKBOARD:\*?\*?)|(?:\n\*?\*?VISUAL_DIRECTIVE:\*?\*?)|(?:\n\*?\*?QUESTION:\*?\*?)|$)/);
    if (narrMatch) {
      narration = narrMatch[1].trim();
    } else if (!bbMatch && !teachingText.match(/\*?\*?BLACKBOARD:\*?\*?/) && !teachingText.match(/\*?\*?NARRATION:\*?\*?/)) {
      // Fallback for completely raw text if tags haven't generated or are missing
      narration = teachingText.trim();
    }
    
    // Globally scrub internal metadata so it never flickers on the learner's screen
    blackboard = blackboard.replace(/USE_PDF_VISUAL:\s*\[?(?:ID\s*)?\d+\]?/gi, '').trim();
    narration = narration.replace(/USE_PDF_VISUAL:\s*\[?(?:ID\s*)?\d+\]?/gi, '').trim();
    
    return { narration, blackboard };
  }, [teachingText]);

  const revealedNarration = useMemo(() => {
    if (!presentationUnits || presentationUnits.length === 0) return "";
    const revealCount = isPlaying ? currentUnitIndex + 1 : currentUnitIndex;
    return presentationUnits
      .slice(0, revealCount)
      .map(u => u.text)
      .join(' ');
  }, [presentationUnits, currentUnitIndex, isPlaying]);

  // If we are actively streaming, we only show narration dictated by the presentation units.
  // If we have finished streaming (or are loading historical session data), we fallback to parsedStream.narration or presentation.voice.narration.
  // If audio is disabled, we fallback to showing the text immediately so the lesson isn't stalled.
  const displayNarration = (isStreaming && audioEnabled) 
    ? revealedNarration 
    : (parsedStream.narration || (presentation ? presentation.voice.narration : ""));
    
  const displayBlackboard = parsedStream.blackboard || (presentation ? presentation.blackboard.content : "");
  const blackboardUrlRaw = presentation ? presentation.blackboard.visual_url : null;
  const blackboardUrl = blackboardUrlRaw 
    ? (blackboardUrlRaw.startsWith('/') ? `${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}${blackboardUrlRaw}` : blackboardUrlRaw)
    : null;
  const blackboardType = presentation ? presentation.blackboard.visual_type : 'markdown';
  
  // Conditionally render video and blackboard based on PresentationDecision
  const teacherVideo = presentation?.teacher_video;
  const provider = teacherVideo?.provider;
  const showVideo = teacherVideo ? teacherVideo.enabled : false; // Default to false if not explicitly enabled
  const showBlackboard = presentation ? presentation.blackboard.enabled : !!displayBlackboard;

  // Manage Audio Owner based on provider
  useEffect(() => {
    if (provider !== 'simli') {
      setAudioOwner('fallback');
    }
  }, [provider]);

  const isVideoVisible = showVideo && provider === 'predefined' && teacherVideo?.url && !videoCompleted;
  const isSimliVisible = showVideo && provider === 'simli';
  const hasTeacherVisible = isVideoVisible || isSimliVisible;

  // Render responsive layout: Blackboard (~70%) on left, Teacher (~30%) on right
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'row',
      flexWrap: 'wrap',
      gap: '1.5rem',
      padding: '2rem',
      flex: 1,
      overflowY: 'auto',
      backgroundColor: '#f8fafc',
      alignItems: 'flex-start'
    }}>
      <audio ref={fallbackAudioRef} style={{ display: 'none' }} />

      {/* Blackboard & Narration Layer (~70%) */}
      <div style={{
        flex: hasTeacherVisible && showBlackboard ? '1 1 60%' : '1 1 100%',
        minWidth: '300px',
        transition: 'all 400ms ease-in-out',
        display: 'flex',
        flexDirection: 'column',
        gap: '1.5rem',
        // Hide if not ready and teacher is prominent
        opacity: (!showBlackboard && !displayNarration) ? 0 : 1
      }}>
        {/* Teacher Narration / Subtitles */}
        {displayNarration && (
          <div className="markdown-body" style={{
            backgroundColor: 'white',
            padding: '1.5rem',
            borderRadius: 'var(--radius-lg)',
            boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1)',
            lineHeight: 1.6,
            color: 'var(--text-primary)',
            fontSize: '1.05rem',
            transition: 'all 400ms ease-in-out'
          }}>
            <ReactMarkdown 
              remarkPlugins={[remarkMath, remarkGfm]} 
              rehypePlugins={[rehypeKatex]}
            >
              {formatMathDelimiters(displayNarration)}
            </ReactMarkdown>
          </div>
        )}

        {/* Blackboard & Visual Container */}
        {showBlackboard && (
          <div style={{ display: 'flex', flexDirection: 'row', gap: '1.5rem', alignItems: 'stretch' }}>
            
            {/* Blackboard Text Content */}
            {(displayBlackboard || blackboardType === 'markdown') && (
              <div style={{
                backgroundColor: '#1e293b',
                padding: '1.5rem',
                borderRadius: 'var(--radius-lg)',
                color: 'white',
                boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                marginTop: '0.5rem',
                flex: ((blackboardType === 'image' || blackboardType === 'pdf_visual') && blackboardUrl) ? '1 1 50%' : '1 1 100%',
                transition: 'all 400ms ease-in-out',
                display: 'flex',
                flexDirection: 'column'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                  <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#94a3b8' }}>
                    BLACKBOARD
                  </div>
                </div>
                
                <div className="markdown-body markdown-body-invert" style={{
                  padding: '1rem',
                  backgroundColor: '#0f172a',
                  borderRadius: 'var(--radius-md)',
                  lineHeight: 1.5,
                  border: '1px solid #334155',
                  flex: 1
                }}>
                  {blackboardType === 'markdown' || ((blackboardType === 'image' || blackboardType === 'pdf_visual') && displayBlackboard) ? (
                    <ReactMarkdown 
                      remarkPlugins={[remarkMath, remarkGfm]} 
                      rehypePlugins={[rehypeKatex]}
                    >
                      {formatMathDelimiters(displayBlackboard || '')}
                    </ReactMarkdown>
                  ) : (
                    displayBlackboard
                  )}
                </div>
              </div>
            )}

            {/* PDF Visual / Image Outside Blackboard */}
            {(blackboardType === 'image' || blackboardType === 'pdf_visual') && blackboardUrl && (
              <div style={{
                flex: '1 1 50%',
                marginTop: '0.5rem',
                borderRadius: 'var(--radius-lg)',
                overflow: 'hidden',
                boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                border: '1px solid #cbd5e1',
                backgroundColor: 'white',
                display: 'flex',
                flexDirection: 'column'
              }}>
                 {presentation?.blackboard.pdf_visual && (
                   <div style={{ fontSize: '0.75rem', color: '#475569', backgroundColor: '#f1f5f9', padding: '0.5rem 1rem', borderBottom: '1px solid #cbd5e1', fontWeight: 600 }}>
                     Source: PDF — Page {presentation.blackboard.pdf_visual.page_number}
                   </div>
                 )}
                 <div style={{ padding: '1rem', flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                   <img 
                     src={blackboardUrl} 
                     alt="Reference Visual"
                     onError={(e) => {
                       const target = e.target as HTMLImageElement;
                       if (!target.src.includes('emergency_fallback.svg')) {
                         target.onerror = null;
                         target.src = '/static/images/emergency_fallback.svg';
                       }
                     }}
                     style={{ maxWidth: '100%', maxHeight: '400px', objectFit: 'contain', borderRadius: '4px' }}
                   />
                 </div>
              </div>
            )}
            
          </div>
        )}
      </div>

      {/* Teacher Video Layer (~30%) */}
      {hasTeacherVisible && (
        <div style={{
          flex: showBlackboard ? '0 0 30%' : '1 1 100%',
          minWidth: '250px',
          transition: 'all 400ms ease-in-out',
          display: 'flex',
          justifyContent: 'center'
        }}>
          <div style={{ flex: '0 0 auto', width: '300px' }}>
            {provider === 'simli' ? (
              <LiveAiTeacher 
                audioUrl={playableAudioUrl} 
                onAudioOwnerChange={setAudioOwner}
                audioEnabled={audioEnabled}
                onAudioPlay={() => setIsPlaying(true)}
                onAudioEnded={handleAudioEnded}
              />
            ) : isVideoVisible ? (
              <PredefinedTeacherVideo 
                url={teacherVideo.url!} 
                onEnded={() => setVideoCompleted(true)}
                muted={!audioEnabled}
              />
            ) : null}
          </div>
        </div>
      )}
    </div>
  )
}
