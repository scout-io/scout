import React, { useState, useEffect } from 'react';
import ModelList from './components/ModelList';
import LogViewer from './components/LogViewer';
import 'bootstrap/dist/css/bootstrap.min.css';
import './App.css';
import Navbar from 'react-bootstrap/Navbar';
import Container from 'react-bootstrap/Container';
import { FaGithub } from 'react-icons/fa';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemText from '@mui/material/ListItemText';
import Box from '@mui/material/Box';
import Switch from '@mui/material/Switch';
import Button from '@mui/material/Button';
import axios from 'axios';
import {
  FaCopy
} from 'react-icons/fa';

// A simple Admin Panel embedded in this file
function AdminPanel() {
  const [isProtected, setIsProtected] = useState(false);
  const [authToken, setAuthToken] = useState(null);
  const [justGeneratedToken, setJustGeneratedToken] = useState('');

  // On mount, check current protection status and token
  useEffect(() => {
    fetchProtectionStatus();
  }, []);

  const fetchProtectionStatus = async () => {
    try {
      const response = await axios.get('/admin/get_protection');
      if (response.data?.protected_api) {
        setIsProtected(true);
      } else {
        setIsProtected(false);
      }
      // We'll store the token locally if we have one
      if (response.data?.auth_token) {
        setAuthToken(response.data.auth_token);
        // Also store it in localStorage so subsequent requests can use it
        localStorage.setItem('authToken', response.data.auth_token);
      } else {
        setAuthToken(null);
        localStorage.removeItem('authToken');
      }
    } catch (error) {
      console.error('Failed to fetch protection status:', error);
    }
  };

  const handleToggleProtection = async () => {
    const newStatus = !isProtected;
    setIsProtected(newStatus);

    try {
      // We send a top-level boolean, e.g. "true" or "false" (as text)
      await axios.post('/admin/set_protection', JSON.stringify(newStatus), {
        headers: {
          'Content-Type': 'application/json',
        },
      });

      // If turning OFF, remove stored token
      if (!newStatus) {
        setAuthToken(null);
        localStorage.removeItem('authToken');
      }
      // else: If turning ON, user can generate a token if needed

    } catch (error) {
      console.error('Failed to set protection status:', error);
    }
  };


  const handleGenerateToken = async () => {
    try {
      const response = await axios.post('/admin/generate_token', {});
      if (response.data?.token) {
        // Show the freshly generated token in the UI, store it in localStorage
        setJustGeneratedToken(response.data.token);
        setAuthToken(response.data.token);
        localStorage.setItem('authToken', response.data.token);
      }
    } catch (error) {
      console.error('Failed to generate token:', error);
    }
  };

  const handleCopyToken = async () => {
    if (justGeneratedToken) {
      await navigator.clipboard.writeText(justGeneratedToken);
    }
  };

  return (
    <div style={{ background: '#151515', padding: '2rem', borderRadius: '8px' }}>
      <h2 style={{ fontFamily: 'Darker Grotesque', marginBottom: '1rem', color: 'white' }}>Admin</h2>

      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '1rem' }}>
        <Switch
          checked={isProtected}
          onChange={handleToggleProtection}
          sx={{
            // Thumb (circle) color when checked
            '& .Mui-checked': {
              color: 'white !important',
            },
            // Track color when checked
            '& .Mui-checked + .MuiSwitch-track': {
              backgroundColor: '#3CBC84 !important',
            },
            // Dark track color when not checked
            '& .MuiSwitch-track': {
              backgroundColor: '#444 !important',
            },
          }}
        />
        <span style={{ marginLeft: '0.5rem', fontFamily: 'Darker Grotesque', fontSize: '16px', color: 'white' }}>
          Protect API with token
        </span>
      </div>

      {isProtected && (
        <>
          <div style={{ marginBottom: '1rem', fontFamily: 'Darker Grotesque' }}>
            <Button variant="contained"
              type="submit"
              sx={{
                backgroundColor: '#333333',
                color: '#FFF',
                fontWeight: 500,
                fontSize: '10pt',
                padding: '8px 16px',
                borderRadius: '8px',
                width: '30%',
                '&:hover': {
                  backgroundColor: '#444444',
                },
              }}
              onClick={handleGenerateToken}>
              Generate New Token
            </Button>
          </div>

          {justGeneratedToken && (
            <div style={{ marginBottom: '1rem', background: '#FFF', padding: '1rem', borderRadius: '4px', backgroundColor: '#333333' }}>
              <div style={{
                fontFamily: 'monospace', fontSize: '14px', color: 'white'
              }}>
                <strong>New Token:</strong> {justGeneratedToken}
                <FaCopy
                  style={{ marginLeft: '10px', cursor: 'pointer', color: '#C0C1C2' }}
                  onClick={handleCopyToken}
                />
              </div>


            </div>
          )
          }

          {/* {
            authToken && !justGeneratedToken && (
              <div style={{ marginBottom: '1rem', background: '#FFF', padding: '1rem', borderRadius: '4px' }}>
                <div style={{ fontFamily: 'Darker Grotesque', fontSize: '14px' }}>
                  <strong>Current Token (from config):</strong> {authToken}
                </div>
              </div>
            )
          } */}
        </>
      )}
    </div >
  );
}

function App() {
  const [currentScreen, setCurrentScreen] = useState('Tests');

  return (
    <>
      <Navbar variant="dark" style={{ width: '100%' }}>
        <Container>
          <Navbar.Brand style={{ fontSize: '20px', fontFamily: 'Darker Grotesque', fontWeight: 400 }}>
            Scout ⌖
          </Navbar.Brand>
          <div className="ms-auto" style={{ display: 'flex', alignItems: 'center' }}>
            <Navbar.Text
              style={{ fontSize: '15px', marginRight: '20px', fontFamily: 'Darker Grotesque', fontWeight: 400 }}
            >
              Docs
            </Navbar.Text>
            <Navbar.Text style={{ fontSize: '15px' }}>
              <a
                href="https://github.com/yourgithubusername/reponame"
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: 'inherit', textDecoration: 'none' }}
              >
                <FaGithub style={{ fontSize: '1.5em' }} />
              </a>
            </Navbar.Text>
          </div>
        </Container>
      </Navbar>

      <Box sx={{ display: 'flex', height: '100vh' }}>
        {/* Sidebar */}
        <Box
          sx={{
            width: '20%',
            bgcolor: '#151515',
            color: '#FFF',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <List component="nav">
            <ListItem disablePadding>
              <ListItemButton
                selected={currentScreen === 'Tests'}
                onClick={() => setCurrentScreen('Tests')}
                sx={{
                  color: '#FFF',
                  '&.Mui-selected': {
                    backgroundColor: '#333333',
                  },
                  '&:hover': {
                    backgroundColor: '#444444',
                  },
                }}
              >
                <ListItemText
                  primary="⎔  Tests"
                  sx={{
                    '& .MuiTypography-root': {
                      fontFamily: 'Darker Grotesque',
                      fontSize: '12pt',
                      textAlign: 'right',
                    },
                  }}
                />
              </ListItemButton>
            </ListItem>
            <ListItem disablePadding>
              <ListItemButton
                selected={currentScreen === 'Admin'}
                onClick={() => setCurrentScreen('Admin')}
                sx={{
                  color: '#FFF',
                  '&.Mui-selected': {
                    backgroundColor: '#333333',
                  },
                  '&:hover': {
                    backgroundColor: '#444444',
                  },
                }}
              >
                <ListItemText
                  primary="⚙︎ Admin"
                  sx={{
                    '& .MuiTypography-root': {
                      fontFamily: 'Darker Grotesque',
                      fontSize: '12pt',
                      textAlign: 'right',
                    },
                  }}
                />
              </ListItemButton>
            </ListItem>
            <ListItem disablePadding>
              <ListItemButton
                selected={currentScreen === 'Logs'}
                onClick={() => setCurrentScreen('Logs')}
                sx={{
                  color: '#FFF',
                  '&.Mui-selected': {
                    backgroundColor: '#333333',
                  },
                  '&:hover': {
                    backgroundColor: '#444444',
                  },
                }}
              >
                <ListItemText
                  primary="✎  Logs"
                  sx={{
                    '& .MuiTypography-root': {
                      fontFamily: 'Darker Grotesque',
                      fontSize: '12pt',
                      textAlign: 'right',
                    },
                  }}
                />
              </ListItemButton>
            </ListItem>
          </List>
        </Box>

        {/* Main Content */}
        <Box sx={{ flexGrow: 1, padding: '2%', paddingLeft: '5%', paddingRight: '20%' }}>
          {currentScreen === 'Logs' ? (
            <LogViewer />
          ) : currentScreen === 'Admin' ? (
            <AdminPanel />
          ) : (
            <ModelList currentScreen={currentScreen} />
          )}
        </Box>
      </Box>
    </>
  );
}

export default App;
