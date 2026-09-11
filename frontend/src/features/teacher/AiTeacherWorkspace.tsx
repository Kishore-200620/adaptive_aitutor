import type { PresentationDecision } from '../../types/api'
import { LiveAiTeacher } from './LiveAiTeacher'
import { PredefinedTeacherVideo } from './PredefinedTeacherVideo'
import { useState, useRef, useEffect, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import remarkGfm from 'remark-gfm';
import 'katex/dist/katex.min.css';

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
  audioEnabled: boolean;
}

export function AiTeacherWorkspace({ teachingText, presentation, audioUrl, audioEnabled }: AiTeacherWorkspaceProps) {
  const [audioOwner, setAudioOwner] = useState<'simli' | 'fallback' | 'none'>('fallback');
  const [videoCompleted, setVideoCompleted] = useState(false);
  const fallbackAudioRef = useRef<HTMLAudioElement>(null);
  const currentClipIdRef = useRef<string | null>(null);

  // Reset videoCompleted when a new clip_id arrives
  useEffect(() => {
    if (presentation?.teacher_video?.clip_id && presentation.teacher_video.clip_id !== currentClipIdRef.current) {
      setVideoCompleted(false);
      currentClipIdRef.current = presentation.teacher_video.clip_id;
    }
  }, [presentation?.teacher_video?.clip_id]);

  // Handle native fallback audio when audioOwner is 'fallback'
  useEffect(() => {
    if (audioOwner === 'fallback' && audioUrl && fallbackAudioRef.current && audioEnabled) {
      const fullAudioUrl = `${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}${audioUrl}`;
      if (fallbackAudioRef.current.src !== fullAudioUrl) {
        fallbackAudioRef.current.src = fullAudioUrl;
        fallbackAudioRef.current.play().catch(e => console.error("Fallback audio play failed", e));
      } else {
        fallbackAudioRef.current.play().catch(e => console.error("Fallback audio play failed", e));
      }
    } else if (fallbackAudioRef.current) {
      fallbackAudioRef.current.pause();
    }
  }, [audioOwner, audioUrl, audioEnabled]);

  const parsedStream = useMemo(() => {
    if (presentation) return null; // Use authoritative presentation if available
    let narration = "";
    let blackboard = "";
    let text = teachingText;
    
    // Simple naive parsing for streaming UI
    if (text.includes("BLACKBOARD:")) {
      const parts = text.split("BLACKBOARD:");
      narration = parts[0].replace("NARRATION:", "").trim();
      blackboard = parts[1].split("VISUAL_DIRECTIVE:")[0].trim();
    } else {
      narration = text.replace("NARRATION:", "").split("VISUAL_DIRECTIVE:")[0].trim();
    }
    
    return { narration, blackboard };
  }, [teachingText, presentation]);

  const displayNarration = presentation ? presentation.voice.narration : parsedStream?.narration;
  const displayBlackboard = presentation ? presentation.blackboard.content : parsedStream?.blackboard;
  const blackboardUrl = presentation ? presentation.blackboard.visual_url : null;
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

        {/* Blackboard Content */}
        {showBlackboard && (
          <div style={{
            backgroundColor: '#1e293b',
            padding: '1.5rem',
            borderRadius: 'var(--radius-lg)',
            color: 'white',
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
            marginTop: '0.5rem',
            transition: 'all 400ms ease-in-out'
          }}>
            <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#94a3b8', marginBottom: '0.75rem' }}>
              BLACKBOARD
            </div>
            
            <div className="markdown-body markdown-body-invert" style={{
              padding: '1rem',
              backgroundColor: '#0f172a',
              borderRadius: 'var(--radius-md)',
              lineHeight: 1.5,
              border: '1px solid #334155'
            }}>
              {blackboardType === 'image' && blackboardUrl ? (
                <img 
                  src={blackboardUrl} 
                  alt="Blackboard Visual"
                  style={{ maxWidth: '100%', height: 'auto', borderRadius: '4px' }}
                />
              ) : blackboardType === 'markdown' ? (
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
      </div>

      {/* Teacher Video Layer (~30%) */}
      {isVideoVisible && (
        <div style={{
          flex: showBlackboard ? '0 0 30%' : '1 1 100%',
          minWidth: '250px',
          transition: 'all 400ms ease-in-out',
          display: 'flex',
          justifyContent: 'center'
        }}>
          <PredefinedTeacherVideo
            url={teacherVideo.url!}
            onEnded={() => setVideoCompleted(true)}
          />
        </div>
      )}

      {/* Simli Video Layer */}
      {isSimliVisible && (
        <div style={{
          flex: showBlackboard ? '0 0 30%' : '1 1 100%',
          minWidth: '250px',
          transition: 'all 400ms ease-in-out',
          display: 'flex',
          justifyContent: 'center'
        }}>
          <div style={{ width: '100%', maxWidth: '400px' }}>
            <LiveAiTeacher 
              audioUrl={audioUrl}
              onAudioOwnerChange={setAudioOwner}
              audioEnabled={audioEnabled}
            />
          </div>
        </div>
      )}
    </div>
  )
}
