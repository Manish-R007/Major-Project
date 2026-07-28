import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import client from '../api/client'
import { useAuth } from '../context/AuthContext.jsx'

const EMPTY_FORM = {
  full_name: '', username: '', email: '', password: '', confirmPassword: '',
  state: '', district: '', village: '',
}

export default function Register() {
  const [form, setForm] = useState(EMPTY_FORM)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')

    if (form.password !== form.confirmPassword) {
      setError('Passwords do not match.')
      return
    }
    if (form.password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }

    setSubmitting(true)
    try {
      await client.post('/auth/register', {
        full_name: form.full_name,
        username: form.username,
        email: form.email || undefined,
        password: form.password,
        state: form.state || undefined,
        district: form.district || undefined,
        village: form.village || undefined,
      })
      // Registration succeeds silently into a Citizen account; log them
      // straight in so they land on their dashboard.
      await login(form.username, form.password)
      navigate('/dashboard')
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not create your account. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-canopy-950 px-6 py-12">
      <div className="pointer-events-none absolute inset-0 opacity-40">
        <svg viewBox="0 0 1200 800" className="h-full w-full" preserveAspectRatio="xMidYMid slice">
          {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
            <path
              key={i}
              d={`M-100 ${120 + i * 90} C 250 ${40 + i * 90}, 550 ${200 + i * 90}, 900 ${90 + i * 90} S 1400 ${140 + i * 90}, 1600 ${90 + i * 90}`}
              fill="none"
              stroke="#6E9C7D"
              strokeOpacity={0.18 - i * 0.012}
              strokeWidth="1.5"
            />
          ))}
        </svg>
      </div>
      <div className="pointer-events-none absolute -left-40 -top-40 h-96 w-96 rounded-full bg-ochre-500/10 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-32 -right-24 h-96 w-96 rounded-full bg-canopy-400/10 blur-3xl" />

      <div className="relative z-10 w-full max-w-xl rounded-3xl border border-parchment-100/10 bg-parchment-100 p-10 shadow-2xl">
        <span className="grid h-11 w-11 place-items-center rounded-full bg-canopy-900 font-display text-lg text-parchment-100">
          FA
        </span>
        <h1 className="mt-6 font-display text-2xl text-canopy-950">Register as a Claimant</h1>
        <p className="mt-1 text-sm text-canopy-700/70">
          Create an account to submit and track your FRA claims. Officials
          are provisioned separately by an administrator.
        </p>

        <form onSubmit={handleSubmit} className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Full Name" value={form.full_name} onChange={(v) => update('full_name', v)} />
          <Field label="Username" value={form.username} onChange={(v) => update('username', v)} />
          <Field label="Email (optional)" type="email" required={false} value={form.email} onChange={(v) => update('email', v)} />
          <div />
          <Field label="Password" type="password" value={form.password} onChange={(v) => update('password', v)} />
          <Field label="Confirm Password" type="password" value={form.confirmPassword} onChange={(v) => update('confirmPassword', v)} />

          <div className="col-span-full mt-2 border-t border-canopy-900/10 pt-4">
            <p className="text-xs font-medium uppercase tracking-wide text-canopy-700/70">
              Location (optional, helps route your claims correctly)
            </p>
          </div>
          <Field label="State" required={false} value={form.state} onChange={(v) => update('state', v)} />
          <Field label="District" required={false} value={form.district} onChange={(v) => update('district', v)} />
          <Field label="Village" required={false} value={form.village} onChange={(v) => update('village', v)} />

          {error && <p className="col-span-full rounded-lg bg-rust-500/10 px-3 py-2 text-sm text-rust-600">{error}</p>}

          <div className="col-span-full mt-2">
            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-lg bg-canopy-900 py-2.5 text-sm font-medium text-parchment-100 transition hover:bg-canopy-800 disabled:opacity-60"
            >
              {submitting ? 'Creating account…' : 'Create Account'}
            </button>
          </div>
        </form>

        <p className="mt-6 text-center text-sm text-canopy-700/70">
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-ochre-600 hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  )
}

const inputClass = "mt-1.5 w-full rounded-lg border border-canopy-900/15 bg-white px-3.5 py-2.5 text-sm text-ink outline-none transition focus:border-ochre-500 focus:ring-2 focus:ring-ochre-400/30"

function Field({ label, value, onChange, type = 'text', required = true }) {
  return (
    <div>
      <label className="text-xs font-medium uppercase tracking-wide text-canopy-800">{label}</label>
      <input
        type={type}
        required={required}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={inputClass}
      />
    </div>
  )
}
