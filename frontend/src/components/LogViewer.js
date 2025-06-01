import React from 'react';
import { LazyLog } from '@melloware/react-logviewer';
import { Box } from '@mui/material';

const LogViewer = () => {

    const formatPart = (text, index) => {
        // Define keywords and their styles
        const keywordStyles = [
            { token: 'ERROR:', color: '#e06c75', fontWeight: 'bold' }, // Soft Red
            { token: 'WARNING:', color: '#d19a66', fontWeight: 'bold' }, // Darker Orange for Warning
            { token: 'INFO:', color: '#61afef', fontWeight: 'bold' },    // Pleasant Blue
            // Add more log levels if needed (e.g., DEBUG, TRACE)
            // { token: 'DEBUG:', color: '#c678dd', fontWeight: 'normal' }, // Purple for Debug
        ];

        for (const { token, color, fontWeight } of keywordStyles) {
            if (text.startsWith(token)) {
                return [
                    <span key={`${index}-keyword`} style={{ color, fontWeight, paddingRight: '8px' }}>{token}</span>,
                    <span key={`${index}-message`} style={{ color: '#abb2bf' }}>{text.substring(token.length)}</span>
                ];
            }
        }
        // Default style for lines that don't match keywords (e.g., multiline messages part of an error)
        return <span key={index} style={{ color: '#abb2bf' }}>{text}</span>;
    };

    return (
        <div>
            <Box
                sx={{
                    borderRadius: '12px',
                    height: '80vh',
                    backgroundColor: 'rgba(21,21,21,1)',
                    padding: '16px',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
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
                    style={{
                        backgroundColor: '#1e1e1e',
                        color: '#d4d4d4',
                        fontSize: '14px',
                        fontFamily: "'Fira Code', 'Consolas', 'Menlo', 'Monaco', monospace",
                        lineHeight: '1.6',
                        borderRadius: '8px',
                    }}
                    formatPart={formatPart}
                />
            </Box>
        </div>
    );
};

export default LogViewer;