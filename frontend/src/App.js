import React, { useState, useEffect } from 'react';
import ModelList from './components/ModelList';
import LogViewer from './components/LogViewer';
import AdminPanel from './components/AdminPanel';
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
import { FaCopy } from 'react-icons/fa';
import { ApiReferenceReact } from '@scalar/api-reference-react'
import '@scalar/api-reference-react/style.css'

function Footer() {
  return (
    <footer
      style={{
        backgroundColor: '#151515',
        color: '#FFF',
        padding: '1rem 2rem',
        textAlign: 'center',
        borderTop: '1px solid #333',
        // position: 'sticky',
        bottom: 0,
        width: '100%',
      }}
    >
      <div style={{ fontFamily: 'Darker Grotesque', fontSize: '14px', lineHeight: '1.5' }}>
        <p style={{ margin: 0 }}>
          &copy; {new Date().getFullYear()} Scout. All rights reserved.
        </p>
        <p style={{ margin: 0 }}>Version 1.0.0</p>
      </div>
    </footer>
  );
}

function App() {
  const [currentScreen, setCurrentScreen] = useState('Tests');

  return (
    <>
      <Navbar variant="dark" style={{ width: '100%' }}>
        <Container>
          <Navbar.Brand
            href="/"
            style={{
              fontSize: '20px',
              fontFamily: 'Darker Grotesque',
              fontWeight: 400,
              cursor: 'pointer',
              textDecoration: 'none'
            }}
          >
            Scout 🝊
          </Navbar.Brand>
          <div className="ms-auto" style={{ display: 'flex', alignItems: 'center' }}>
            <Navbar.Text
              style={{ fontSize: '15px', marginRight: '20px', fontFamily: 'Darker Grotesque', fontWeight: 400 }}
            >
              Docs
            </Navbar.Text>
            <Navbar.Text style={{ fontSize: '15px' }}>
              <a
                href="https://github.com/scout-io/scout"
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

      <Box sx={{ display: 'flex', minHeight: '100vh' }}>
        {/* Sidebar */}
        <Box
          sx={{
            width: '20%',
            bgcolor: '#151515',
            color: '#FFF',
            display: 'flex',
            flexDirection: 'column'
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
                selected={currentScreen === 'API Sandbox'}
                onClick={() => setCurrentScreen('API Sandbox')}
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
                  primary="𐄳  API Sandbox"
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
        <Box
          sx={{
            flexGrow: 1,
            padding: '2%',
            paddingLeft: '5%',
            paddingRight: currentScreen === 'API Sandbox' ? '5%' : '20%', // Conditional padding
          }}
        >
          {currentScreen === 'Logs' ? (
            <LogViewer />
          ) : currentScreen === 'Admin' ? (
            <AdminPanel />
          ) : currentScreen === 'API Sandbox' ? (
            <div
              style={{
                '--scalar-background-1': '#151515',
                borderRadius: '8px',
                overflow: 'hidden'
              }}
            >
              <ApiReferenceReact
                configuration={{
                  spec: {
                    url: '/openapi',
                  },
                  hideClientButton: true,
                  hideDownloadButton: true,
                  hideModels: true,
                  hideSearch: true,
                  darkMode: true,
                  hideDarkModeToggle: true,
                  theme: 'none',
                }}
              />
            </div>
          ) : (
            <ModelList currentScreen={currentScreen} />
          )}
        </Box>
      </Box>
      <Footer />
    </>
  );
}

export default App;
