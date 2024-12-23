import React from 'react';
import { LazyLog } from 'react-lazylog';
import { Box } from '@mui/material';

const LogViewer = () => {

    const formatPart = (part, index) => {
        if (part.includes('ERROR:')) {
            return <span key={index} style={{ color: 'red' }}>{part}</span>;
        } else if (part.includes('INFO:')) {
            return <span key={index} style={{ color: 'green' }}>{part}</span>;
        }
        else if (part.includes('WARNING:')) {
            return <span key={index} style={{ color: 'orange' }}>{part}</span>;
        }
        return <span key={index}>{part}</span>;
    };

    return (
        <div>
            <Box
                sx={{
                    borderRadius: '40px',
                    height: '80vh',
                    backgroundColor: '#1e1e1e',
                }}
            >
                <LazyLog
                    url="/logs/stream"
                    stream
                    follow
                    selectableLines
                    extraLines={1}
                    enableSearch
                    caseInsensitive
                    style={{ backgroundColor: '#151515', color: '#fff', fontSize: '14px', fontFamily: 'monospace' }}
                    formatPart={formatPart} // Apply styling to each line
                />
            </Box>
        </div>
    );
};

export default LogViewer;