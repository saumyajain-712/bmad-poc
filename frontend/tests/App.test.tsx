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
        run: {
          id: 42,
          api_specification: 'Create a todo API',
          status: 'initiated',
          missing_items: [],
          clarification_questions: [],
        },
        validation: {
          is_complete: true,
          missing_items: [],
          clarification_questions: [],
        },
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

  it('shows clarification prompts when input is incomplete', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({
        run: {
          id: 77,
          api_specification: 'tiny',
          status: 'awaiting-clarification',
          missing_items: ['meaningful detail length'],
          clarification_questions: [
            'Which operations should the API support for each resource (for example create, read, update, delete, or list)?',
            'Which specific resources should this API manage (for example users, products, orders, or todos)?',
          ],
        },
        validation: {
          is_complete: false,
          missing_items: ['supported operations', 'target resources'],
          clarification_questions: [
            'Which specific resources should this API manage (for example users, products, orders, or todos)?',
            'Which operations should the API support for each resource (for example create, read, update, delete, or list)?',
          ],
        },
      }),
    } as Response);

    render(<App />);
    fireEvent.change(
      screen.getByPlaceholderText(/Enter free-text API specification/i),
      { target: { value: 'tiny' } }
    );
    fireEvent.click(screen.getByRole('button', { name: /Initiate BMAD Run/i }));

    expect(
      await screen.findByText(
        /Input clarification required before continuation\. Run ID: 77, Status: awaiting-clarification/i
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Workflow paused: provide clarifications to continue\./i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /Which operations should the API support for each resource \(for example create, read, update, delete, or list\)\?/i
      )
    ).toBeInTheDocument();
    const items = screen.getAllByRole('listitem');
    expect(items[0]).toHaveTextContent(
      /Which operations should the API support for each resource \(for example create, read, update, delete, or list\)\?/i
    );
    expect(items[1]).toHaveTextContent(
      /Which specific resources should this API manage \(for example users, products, orders, or todos\)\?/i
    );
    expect(screen.getByRole('button', { name: /Submit Clarifications/i })).toBeInTheDocument();
  });

  it('submits clarification answers for the same run', async () => {
    vi.spyOn(global, 'fetch')
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          run: {
            id: 90,
            api_specification: 'Create API for data',
            status: 'awaiting-clarification',
            missing_items: ['supported operations'],
            clarification_questions: [
              'Which operations should the API support for each resource (for example create, read, update, delete, or list)?',
            ],
          },
          validation: {
            is_complete: false,
            missing_items: ['supported operations'],
            clarification_questions: [
              'Which operations should the API support for each resource (for example create, read, update, delete, or list)?',
            ],
          },
        }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          run: {
            id: 90,
            api_specification: 'Create API for data with CRUD',
            status: 'initiated',
            missing_items: [],
            clarification_questions: [],
          },
          validation: {
            is_complete: true,
            missing_items: [],
            clarification_questions: [],
          },
        }),
      } as Response);

    render(<App />);
    fireEvent.change(
      screen.getByPlaceholderText(/Enter free-text API specification/i),
      { target: { value: 'Create API for data' } }
    );
    fireEvent.click(screen.getByRole('button', { name: /Initiate BMAD Run/i }));

    const answerInput = await screen.findByPlaceholderText(/Provide clarification response/i);
    fireEvent.change(answerInput, { target: { value: 'CRUD for users with required fields name and email' } });
    fireEvent.click(screen.getByRole('button', { name: /Submit Clarifications/i }));

    expect(
      await screen.findByText(/Run resumed successfully! Run ID: 90, Status: initiated/i)
    ).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/Provide clarification response/i)).not.toBeInTheDocument();
  });

  it('requires all clarification answers before submission', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        run: {
          id: 91,
          api_specification: 'Create API for data',
          status: 'awaiting-clarification',
          missing_items: ['supported operations', 'target resources'],
          clarification_questions: [
            'Which operations should the API support for each resource (for example create, read, update, delete, or list)?',
            'Which specific resources should this API manage (for example users, products, orders, or todos)?',
          ],
        },
        validation: {
          is_complete: false,
          missing_items: ['supported operations', 'target resources'],
          clarification_questions: [
            'Which operations should the API support for each resource (for example create, read, update, delete, or list)?',
            'Which specific resources should this API manage (for example users, products, orders, or todos)?',
          ],
        },
      }),
    } as Response);

    render(<App />);
    fireEvent.change(
      screen.getByPlaceholderText(/Enter free-text API specification/i),
      { target: { value: 'Create API for data' } }
    );
    fireEvent.click(screen.getByRole('button', { name: /Initiate BMAD Run/i }));

    await screen.findByText(/Input clarification required before continuation/i);
    fireEvent.click(screen.getByRole('button', { name: /Submit Clarifications/i }));

    expect(
      await screen.findByText(/Please answer all clarification questions before continuing\./i)
    ).toBeInTheDocument();
  });

  it('gracefully handles missing clarification question array', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({
        run: {
          id: 88,
          api_specification: 'tiny',
          status: 'awaiting-clarification',
          missing_items: ['supported operations'],
          clarification_questions: [],
        },
        validation: {
          is_complete: false,
          missing_items: ['supported operations'],
          clarification_questions: null,
        },
      }),
    } as Response);

    render(<App />);
    fireEvent.change(
      screen.getByPlaceholderText(/Enter free-text API specification/i),
      { target: { value: 'tiny' } }
    );
    fireEvent.click(screen.getByRole('button', { name: /Initiate BMAD Run/i }));

    expect(
      await screen.findByText(
        /Input clarification required before continuation\. Run ID: 88, Status: awaiting-clarification/i
      )
    ).toBeInTheDocument();
    expect(screen.getByText(/Workflow paused: provide clarifications to continue\./i)).toBeInTheDocument();
    expect(screen.queryByRole('listitem')).not.toBeInTheDocument();
  });

  it('shows paused warning when validation is incomplete even with unexpected run status', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({
        run: {
          id: 89,
          api_specification: 'tiny',
          status: 'initiated',
          missing_items: ['supported operations'],
          clarification_questions: [],
        },
        validation: {
          is_complete: false,
          missing_items: ['supported operations'],
          clarification_questions: [
            'Which operations should the API support for each resource (for example create, read, update, delete, or list)?',
          ],
        },
      }),
    } as Response);

    render(<App />);
    fireEvent.change(
      screen.getByPlaceholderText(/Enter free-text API specification/i),
      { target: { value: 'tiny' } }
    );
    fireEvent.click(screen.getByRole('button', { name: /Initiate BMAD Run/i }));

    expect(
      await screen.findByText(
        /Input clarification required before continuation\. Run ID: 89, Status: initiated/i
      )
    ).toBeInTheDocument();
    expect(screen.getByText(/Workflow paused: provide clarifications to continue\./i)).toBeInTheDocument();
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
