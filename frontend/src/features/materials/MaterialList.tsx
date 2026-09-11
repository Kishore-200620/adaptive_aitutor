import { useState, useRef, useEffect } from 'react';
import { eduvaApi } from '../../lib/api';
import { storage } from '../../lib/storage';
import type { LocalMaterial } from '../../lib/storage';

interface MaterialListProps {
  onSelectMaterial: (documentId: number, filename: string) => void;
  disabled?: boolean;
}

export function MaterialList({ onSelectMaterial, disabled }: MaterialListProps) {
  const [materials, setMaterials] = useState<LocalMaterial[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setMaterials(storage.getMaterials());
  }, []);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.type !== 'application/pdf') {
      setError('Only PDF files are supported.');
      return;
    }

    setIsUploading(true);
    setError(null);

    try {
      const response = await eduvaApi.uploadDocument(file);
      const newMaterial: LocalMaterial = {
        document_id: response.document_id,
        filename: response.filename,
        uploaded_at: new Date().toISOString()
      };
      storage.saveMaterial(newMaterial);
      setMaterials(storage.getMaterials());
      
      // Reset input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (err: unknown) {
      const e = err as Error;
      setError(e.message || 'PDF upload failed. Please try again.');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="sidebar-section">
      <h3 className="sidebar-title">My Materials</h3>
      
      <div style={{ marginBottom: '1rem' }}>
        <input 
          type="file" 
          accept=".pdf" 
          ref={fileInputRef}
          onChange={handleFileChange}
          style={{ display: 'none' }} 
          disabled={isUploading || disabled}
        />
        <button 
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading || disabled}
          style={{
            width: '100%',
            padding: '0.75rem',
            backgroundColor: '#f1f5f9',
            border: '1px dashed #cbd5e1',
            borderRadius: 'var(--radius-md)',
            color: 'var(--text-secondary)',
            fontWeight: 500,
            cursor: (isUploading || disabled) ? 'not-allowed' : 'pointer',
            opacity: (isUploading || disabled) ? 0.7 : 1
          }}
        >
          {isUploading ? 'Uploading PDF...' : 'Upload PDF'}
        </button>
        {error && <div style={{ marginTop: '0.5rem', color: 'var(--danger-color)', fontSize: '0.875rem' }}>{error}</div>}
      </div>

      {materials.length === 0 ? (
        <div style={{ color: 'var(--text-muted)', fontSize: '0.875rem', lineHeight: 1.5, padding: '1rem', backgroundColor: 'var(--bg-primary)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)', textAlign: 'center' }}>
          No materials yet. <br/>Upload a PDF to start learning from your own material.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {materials.map((mat) => (
            <MaterialItem 
              key={mat.document_id} 
              mat={mat} 
              onSelectMaterial={onSelectMaterial} 
              disabled={isUploading || disabled} 
            />
          ))}
        </div>
      )}
    </div>
  );
}

function MaterialItem({ mat, onSelectMaterial, disabled }: { mat: LocalMaterial, onSelectMaterial: any, disabled: boolean | undefined }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div style={{ padding: '0.5rem 0.75rem', backgroundColor: '#f8fafc', borderRadius: 'var(--radius-md)', border: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <div style={{ fontSize: '0.875rem', fontWeight: 500, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flex: 1, paddingRight: '0.5rem' }}>
        {mat.filename}
      </div>
      <div style={{ position: 'relative' }} ref={menuRef}>
        <button 
          onClick={() => setMenuOpen(!menuOpen)}
          disabled={disabled}
          style={{
            background: 'transparent',
            border: 'none',
            cursor: disabled ? 'not-allowed' : 'pointer',
            padding: '0.25rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--text-secondary)'
          }}
        >
          ⋮
        </button>
        {menuOpen && (
          <div style={{ position: 'absolute', right: 0, top: '100%', marginTop: '0.25rem', backgroundColor: 'white', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)', zIndex: 10, minWidth: '120px', overflow: 'hidden' }}>
            <button
              onClick={() => {
                onSelectMaterial(mat.document_id, mat.filename);
                setMenuOpen(false);
              }}
              style={{ width: '100%', textAlign: 'left', padding: '0.5rem 0.75rem', background: 'transparent', border: 'none', borderBottom: '1px solid var(--border-color)', cursor: 'pointer', fontSize: '0.875rem', color: 'var(--text-primary)' }}
            >
              Select Context
            </button>
            <button
              onClick={() => setMenuOpen(false)}
              style={{ width: '100%', textAlign: 'left', padding: '0.5rem 0.75rem', background: 'transparent', border: 'none', cursor: 'pointer', fontSize: '0.875rem', color: 'var(--text-secondary)' }}
            >
              View Details
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
