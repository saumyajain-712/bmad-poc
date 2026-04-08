import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../src/App';

describe('App', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the title and run initiation form', () => {
    render(<App />);
    expect(screen.getByText(/BMAD Run Initiator/i)).toBeInTheDocument();
    expect(screen.getByText(/Initiate New BMAD Run/i)).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/Enter free-text API specification/i)
    ).toBeInTheDocument();
  });

  it('shows validation error when submitting empty specification', async () => {
    const fetchSpy = vi.spyOn(global, 'fetch');

    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: /Initiate BMAD Run/i }));

    expect(
      await screen.findByText(/API Specification cannot be empty\./i)
    ).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('submits the form and shows success message', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 42,
        api_specification: 'Create a todo API',
        status: 'initiated',
      }),
    } as Response);

    render(<App />);
    fireEvent.change(
      screen.getByPlaceholderText(/Enter free-text API specification/i),
      { target: { value: 'Create a todo API' } }
    );
    fireEvent.click(screen.getByRole('button', { name: /Initiate BMAD Run/i }));

    expect(
      await screen.findByText(/Run initiated successfully! Run ID: 42, Status: initiated/i)
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(
        screen.getByPlaceholderText(/Enter free-text API specification/i)
      ).toHaveValue('');
    });
  });

  it('shows error message when API call fails', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    } as Response);

    render(<App />);
    fireEvent.change(
      screen.getByPlaceholderText(/Enter free-text API specification/i),
      { target: { value: 'Create a todo API' } }
    );
    fireEvent.click(screen.getByRole('button', { name: /Initiate BMAD Run/i }));

    expect(
      await screen.findByText(/Failed to initiate run\. Please try again\./i)
    ).toBeInTheDocument();
  });

  it('shows error message when fetch rejects (network failure)', async () => {
    vi.spyOn(global, 'fetch').mockRejectedValue(new Error('network error'));

    render(<App />);
    fireEvent.change(
      screen.getByPlaceholderText(/Enter free-text API specification/i),
      { target: { value: 'Create a todo API' } }
    );
    fireEvent.click(screen.getByRole('button', { name: /Initiate BMAD Run/i }));

    expect(
      await screen.findByText(/Failed to initiate run\. Please try again\./i)
    ).toBeInTheDocument();
  });
});
