import React, { useState } from 'react';
import { createRun } from '../../services/bmadService';

const RunInitiationForm: React.FC = () => {
  const [apiSpec, setApiSpec] = useState<string>('');
  const [message, setMessage] = useState<string>('');
  const [error, setError] = useState<string>('');

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setMessage('');
    setError('');

    if (!apiSpec.trim()) {
      setError('API Specification cannot be empty.');
      return;
    }

    try {
      const newRun = await createRun(apiSpec);
      setMessage(`Run initiated successfully! Run ID: ${newRun.id}, Status: ${newRun.status}`);
      setApiSpec('');
    } catch (err) {
      setError('Failed to initiate run. Please try again.');
      console.error(err);
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '10px', maxWidth: '500px', margin: '20px auto' }}>
      <h2>Initiate New BMAD Run</h2>
      <textarea
        value={apiSpec}
        onChange={(e) => setApiSpec(e.target.value)}
        placeholder="Enter free-text API specification (e.g., 'Create a Todo API with CRUD operations')"
        rows={10}
        style={{ width: '100%', padding: '8px', border: '1px solid #ccc', borderRadius: '4px' }}
      ></textarea>
      <button type="submit" style={{ padding: '10px 15px', backgroundColor: '#007bff', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
        Initiate BMAD Run
      </button>
      {message && <p style={{ color: 'green' }}>{message}</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}
    </form>
  );
};

export default RunInitiationForm;
