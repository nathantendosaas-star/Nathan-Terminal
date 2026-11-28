import { FormEvent, useEffect, useState } from "react";
const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
type AuthStatus = { auth_required: boolean; setup_required: boolean; authenticated: boolean };
export default function AuthGate({ children }: { children: React.ReactNode }) {
  const [ready,setReady]=useState(false),[required,setRequired]=useState(false),[setup,setSetup]=useState(false);
  const [password,setPassword]=useState(""),[confirmPassword,setConfirmPassword]=useState(""),[error,setError]=useState(""),[busy,setBusy]=useState(false);
  useEffect(()=>{let active=true;const token=sessionStorage.getItem("nt_access_token")||"";
    fetch(API_BASE+"/api/v1/auth/status",{headers:token?{Authorization:"Bearer "+token}:{}})
      .then(r=>{if(!r.ok)throw new Error("Unable to verify terminal access.");return r.json() as Promise<AuthStatus>;})
      .then(status=>{if(!active)return;setRequired(status.auth_required);setSetup(status.setup_required);if(status.auth_required&&!status.authenticated)sessionStorage.removeItem("nt_access_token");setReady(true);})
      .catch(()=>{if(active){setError("Backend unavailable. Check the API service and try again.");setReady(true);}});
    return()=>{active=false;};
  },[]);
  const submit=async(event:FormEvent)=>{event.preventDefault();if(setup&&password!==confirmPassword){setError("The passwords do not match.");return;}
    setBusy(true);setError("");try{const endpoint=setup?"/api/v1/auth/setup":"/api/v1/auth/login";
      const response=await fetch(API_BASE+endpoint,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({password})});
      const body=await response.json().catch(()=>({}));if(!response.ok)throw new Error(body.detail||(setup?"Password setup failed.":"Login failed."));
      sessionStorage.setItem("nt_access_token",body.access_token);setPassword("");setConfirmPassword("");window.location.reload();
    }catch(err){setError(err instanceof Error?err.message:"Unable to secure terminal.");}finally{setBusy(false);}
  };
  if(!ready)return <div className="auth-screen"><div className="auth-card">SECURELY CONNECTING TO NATHAN TERMINAL…</div></div>;
  if(!required&&!setup)return <>{children}</>;
  if(sessionStorage.getItem("nt_access_token"))return <div className="auth-app"><button className="auth-lock" onClick={()=>{sessionStorage.removeItem("nt_access_token");window.location.reload();}}>Lock terminal</button>{children}</div>;
  return <div className="auth-screen"><form className="auth-card" onSubmit={submit}>
    <div className="auth-mark">N</div><div className="auth-kicker">{setup?"FIRST-TIME SECURITY SETUP":"PRIVATE WORKSPACE"}</div>
    <h1>{setup?"Create your password":"Nathan Terminal"}</h1>
    <p>{setup?"Set a private password for this terminal. It is sent securely to the backend, hashed there, and never stored in your browser or GitHub.":"Enter your password to access your personal market intelligence terminal."}</p>
    <label htmlFor="terminal-password">{setup?"CREATE PASSWORD":"PASSWORD"}</label>
    <input id="terminal-password" type="password" autoComplete={setup?"new-password":"current-password"} minLength={setup?12:1} value={password} onChange={e=>setPassword(e.target.value)} required autoFocus/>
    {setup&&<><label htmlFor="terminal-password-confirm">CONFIRM PASSWORD</label><input id="terminal-password-confirm" type="password" autoComplete="new-password" minLength={12} value={confirmPassword} onChange={e=>setConfirmPassword(e.target.value)} required/></>}
    {error&&<div className="auth-error">{error}</div>}
    <button type="submit" disabled={busy||!password||(setup&&!confirmPassword)}>{busy?(setup?"Securing terminal…":"Verifying…"):(setup?"Secure my terminal":"Unlock terminal")}</button>
    <small>{setup?"At least 12 characters · Stored securely on the backend":"Private access · Sessions expire after 12 hours"}</small>
  </form></div>;
}