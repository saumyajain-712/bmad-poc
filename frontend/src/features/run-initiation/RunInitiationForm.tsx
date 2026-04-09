import React, { useState } from 'react';
import { createRun } from '../../services/bmadService';

const RunInitiationForm: React.FC = () => {
  const [apiSpec, setApiSpec] = useState<string>('');
  const [message, setMessage] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [clarificationQuestions, setClarificationQuestions] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (isSubmitting) {
      return;
    }

    setMessage('');
    setError('');
    setClarificationQuestions([]);

    if (!apiSpec.trim()) {
      setError('API Specification cannot be empty.');
      return;
    }

    try {
      setIsSubmitting(true);
      const response = await createRun(apiSpec);
      const newRun = response.run;
      if (response.validation.is_complete) {
        setMessage(`Run initiated successfully! Run ID: ${newRun.id}, Status: ${newRun.status}`);
        setApiSpec('');
        return;
      }

      setMessage(`Input clarification required. Run ID: ${newRun.id}, Status: ${newRun.status}`);
      setClarificationQuestions(response.validation.clarification_questions);
    } catch (err) {
      setError('Failed to initiate run. Please try again.');
      console.error(err);
    } finally {
      setIsSubmitting(false);
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
      <button
        type="submit"
        disabled={isSubmitting}
        style={{ padding: '10px 15px', backgroundColor: '#007bff', color: 'white', border: 'none', borderRadius: '4px', cursor: isSubmitting ? 'not-allowed' : 'pointer', opacity: isSubmitting ? 0.7 : 1 }}
      >
        Initiate BMAD Run
      </button>
      {message && <p style={{ color: 'green' }}>{message}</p>}
      {clarificationQuestions.length > 0 && (
        <div style={{ border: '1px solid #f0ad4e', borderRadius: '4px', padding: '10px', backgroundColor: '#fff8e1' }}>
          <p style={{ marginTop: 0 }}><strong>Please clarify:</strong></p>
          <ul style={{ marginBottom: 0 }}>
            {clarificationQuestions.map((question, index) => (
              <li key={`${question}-${index}`}>{question}</li>
            ))}
          </ul>
        </div>
      )}
      {error && <p style={{ color: 'red' }}>{error}</p>}
    </form>
  );
};

export default RunInitiationForm;
