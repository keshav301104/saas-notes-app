import React, { useState, useEffect } from 'react';

const App = () => {
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [notes, setNotes] = useState([]);
  const [isNotesLoading, setIsNotesLoading] = useState(false);
  const [error, setError] = useState('');
  const [formState, setFormState] = useState({ title: '', content: '' });

  // Load backend URL from environment variable, fallback to localhost
  const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:3001';

  // State for login form
  const [loginForm, setLoginForm] = useState({ email: '', password: '' });

  // --- Utility Functions ---

  const validateResponse = async (response) => {
    if (response.ok) {
      return response.json();
    }
    const err = await response.json();
    throw new Error(err.message || 'Something went wrong');
  };

  const getAuthHeaders = () => ({
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  });

  // --- Auth Logic ---

  useEffect(() => {
    const storedToken = localStorage.getItem('token');
    const storedUser = JSON.parse(localStorage.getItem('user'));
    if (storedToken && storedUser) {
      setToken(storedToken);
      setUser(storedUser);
    }
  }, []);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const response = await fetch(`${BACKEND_URL}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(loginForm)
      });
      const data = await validateResponse(response);
      setToken(data.token);
      setUser(data.user);
      localStorage.setItem('token', data.token);
      localStorage.setItem('user', JSON.stringify(data.user));
    } catch (err) {
      setError(err.message);
    }
  };

  const handleLogout = () => {
    setToken(null);
    setUser(null);
    setNotes([]);
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setError('');
  };
  
  // --- Notes Logic ---
  
  useEffect(() => {
    if (token) {
      fetchNotes();
    }
  }, [token]);

  const fetchNotes = async () => {
    setIsNotesLoading(true);
    setError('');
    try {
      const response = await fetch(`${BACKEND_URL}/notes`, {
        headers: getAuthHeaders(),
      });
      const data = await validateResponse(response);
      setNotes(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsNotesLoading(false);
    }
  };

  const handleCreateNote = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const response = await fetch(`${BACKEND_URL}/notes`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(formState)
      });
      const data = await validateResponse(response);
      setNotes([data, ...notes]);
      setFormState({ title: '', content: '' });
    } catch (err) {
      setError(err.message);
    }
  };
  
  const handleDeleteNote = async (id) => {
    setError('');
    try {
      await fetch(`${BACKEND_URL}/notes/${id}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      });
      setNotes(notes.filter(note => note.id !== id));
    } catch (err) {
      setError(err.message);
    }
  };

  const handleUpgrade = async (slug) => {
    setError('');
    try {
      await fetch(`${BACKEND_URL}/tenants/${slug}/upgrade`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });
      // Refresh the page or update user state to reflect the change
      window.location.reload(); 
    } catch (err) {
      setError(err.message);
    }
  };


  // --- UI Components ---
  const renderLogin = () => (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100 p-4">
      <div className="w-full max-w-md bg-white rounded-xl shadow-lg p-8">
        <h1 className="text-3xl font-bold text-center text-gray-800 mb-6">SaaS Notes App</h1>
        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-gray-700 text-sm font-bold mb-2" htmlFor="email">
              Email
            </label>
            <input
              type="email"
              id="email"
              className="shadow appearance-none border rounded-xl w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="admin@acme.test"
              value={loginForm.email}
              onChange={(e) => setLoginForm({ ...loginForm, email: e.target.value })}
              required
            />
          </div>
          <div>
            <label className="block text-gray-700 text-sm font-bold mb-2" htmlFor="password">
              Password
            </label>
            <input
              type="password"
              id="password"
              className="shadow appearance-none border rounded-xl w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="password"
              value={loginForm.password}
              onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })}
              required
            />
          </div>
          <button
            type="submit"
            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-2 px-4 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-opacity-50 transition duration-300"
          >
            Login
          </button>
        </form>
        {error && <p className="text-red-500 text-center mt-4">{error}</p>}
      </div>
    </div>
  );

  const renderDashboard = () => (
    <div className="min-h-screen bg-gray-100 p-8">
      <div className="max-w-4xl mx-auto">
        <header className="flex justify-between items-center mb-6">
          <div className="flex items-center space-x-4">
            <h1 className="text-3xl font-bold text-gray-800">My Notes</h1>
            <span className="bg-indigo-100 text-indigo-800 text-sm font-semibold px-2.5 py-0.5 rounded-full">
              {user.role} | {user.tenant_id}
            </span>
            {user.role === 'Admin' && <span className="bg-green-100 text-green-800 text-sm font-semibold px-2.5 py-0.5 rounded-full">
              Pro Plan
            </span>}
            {user.role === 'Member' && <span className="bg-yellow-100 text-yellow-800 text-sm font-semibold px-2.5 py-0.5 rounded-full">
              Free Plan
            </span>}
          </div>
          <div className="flex space-x-4">
            {user.role === 'Admin' && (
              <button
                onClick={() => handleUpgrade(user.tenant_id)}
                className="bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-4 rounded-xl transition duration-300"
              >
                Upgrade to Pro
              </button>
            )}
            <button
              onClick={handleLogout}
              className="bg-red-600 hover:bg-red-700 text-white font-bold py-2 px-4 rounded-xl transition duration-300"
            >
              Logout
            </button>
          </div>
        </header>

        {error && <p className="text-red-500 text-center mb-4">{error}</p>}

        <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-800 mb-4">Create New Note</h2>
          <form onSubmit={handleCreateNote} className="space-y-4">
            <div>
              <label className="block text-gray-700 text-sm font-bold mb-2" htmlFor="note-title">
                Title
              </label>
              <input
                type="text"
                id="note-title"
                className="shadow appearance-none border rounded-xl w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="Note Title"
                value={formState.title}
                onChange={(e) => setFormState({ ...formState, title: e.target.value })}
                required
              />
            </div>
            <div>
              <label className="block text-gray-700 text-sm font-bold mb-2" htmlFor="note-content">
                Content
              </label>
              <textarea
                id="note-content"
                className="shadow appearance-none border rounded-xl w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-indigo-500 h-32"
                placeholder="Note Content"
                value={formState.content}
                onChange={(e) => setFormState({ ...formState, content: e.target.value })}
                required
              ></textarea>
            </div>
            <button
              type="submit"
              className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-2 px-4 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-opacity-50 transition duration-300"
            >
              Create Note
            </button>
          </form>
        </div>

        <h2 className="text-xl font-semibold text-gray-800 mb-4">My Notes</h2>
        {isNotesLoading && <p className="text-center text-gray-600">Loading notes...</p>}
        {!isNotesLoading && notes.length === 0 && <p className="text-center text-gray-600">No notes found. Create one above!</p>}
        <div className="grid grid-cols-1 gap-4">
          {notes.map(note => (
            <div key={note.id} className="bg-white rounded-xl shadow-lg p-6 flex flex-col sm:flex-row justify-between items-start sm:items-center">
              <div className="flex-grow">
                <h3 className="text-lg font-bold text-gray-800">{note.title}</h3>
                <p className="text-gray-600 mt-2">{note.content}</p>
                <small className="text-gray-400 block mt-2">
                  Created at: {new Date(note.created_at).toLocaleString()}
                </small>
              </div>
              <button
                onClick={() => handleDeleteNote(note.id)}
                className="bg-red-500 hover:bg-red-600 text-white font-bold py-1 px-3 rounded-lg mt-4 sm:mt-0 ml-0 sm:ml-4 transition duration-300"
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen">
      <script src="https://cdn.tailwindcss.com"></script>
      {token ? renderDashboard() : renderLogin()}
    </div>
  );
};

export default App;
