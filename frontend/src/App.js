import React, { useState } from 'react';
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
          {/* 2) Conditionally render either your ModelList or the Logs Viewer */}
          {currentScreen === 'Logs' ? (
            <LogViewer />
          ) : (
            <ModelList currentScreen={currentScreen} />
          )}
        </Box>
      </Box>
    </>
  );
}

export default App;
