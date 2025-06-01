import React, { useState, useEffect } from 'react';
import {
    Box,
    Card,
    CardContent,
    Typography,
    Switch,
    Button,
    Divider,
    TextField,
    Accordion,
    AccordionSummary,
    AccordionDetails,
    Alert,
    Snackbar,
    CircularProgress,
} from '@mui/material';
import { FaCopy, FaChevronDown } from 'react-icons/fa';
import axios from 'axios';

// Styled components for consistent theme
const SectionTitle = ({ children }) => (
    <Typography
        variant="h6"
        sx={{
            fontFamily: 'Darker Grotesque',
            fontSize: '16pt',
            color: 'white',
            marginBottom: '1rem'
        }}
    >
        {children}
    </Typography>
);

const SubTitle = ({ children }) => (
    <Typography
        variant="subtitle1"
        sx={{
            fontFamily: 'Darker Grotesque',
            fontSize: '14pt',
            color: '#C0C1C2',
            marginBottom: '0.5rem'
        }}
    >
        {children}
    </Typography>
);

// Add default values object after the styled components and before the AdminPanel function
const defaultValues = {
    redis: {
        host: 'localhost',
        port: 6379,
        ttl: 86400,
    },
    model: {
        timeWindowMinutes: 60,
        bucketGranularitySeconds: 60,
        minUpdateRequests: 10,
    },
    system: {
        host: '127.0.0.1',
        port: 8000,
        debug: false,
    }
};

const ConfigTextField = ({ label, value, onChange, disabled = false, isDefault = false }) => (
    <TextField
        label={label}
        value={value}
        onChange={onChange}
        variant="outlined"
        size="small"
        disabled={disabled}
        sx={{
            marginBottom: '1rem',
            '& .MuiOutlinedInput-root': {
                color: isDefault ? '#666666' : 'white',
                fontFamily: 'Darker Grotesque',
                fontSize: '12pt',
                '& fieldset': {
                    borderColor: '#333333',
                },
                '&:hover fieldset': {
                    borderColor: '#444444',
                },
                '&.Mui-focused fieldset': {
                    borderColor: '#3CBC84',
                },
            },
            '& .MuiInputLabel-root': {
                color: isDefault ? '#666666' : '#C0C1C2',
                fontFamily: 'Darker Grotesque',
                '&.Mui-focused': {
                    color: '#3CBC84',
                },
            },
        }}
    />
);

function AdminPanel() {
    // State for API Protection
    const [isProtected, setIsProtected] = useState(false);
    const [authToken, setAuthToken] = useState(null);
    const [justGeneratedToken, setJustGeneratedToken] = useState('');

    // State for Redis Configuration
    const [redisConfig, setRedisConfig] = useState({
        host: 'localhost',
        port: 6379,
        ttl: 86400,
        isHealthy: false,
        keysCount: 0,
    });

    // State for Model Configuration
    const [modelConfig, setModelConfig] = useState({
        timeWindowMinutes: 60,
        bucketGranularitySeconds: 60,
        minUpdateRequests: 10,
    });

    // State for System Configuration
    const [systemConfig, setSystemConfig] = useState({
        host: '127.0.0.1',
        port: 8000,
        debug: false,
    });

    // Notification state
    const [notification, setNotification] = useState({
        open: false,
        message: '',
        severity: 'success',
    });

    // Loading states
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);

    // Add state to track original and modified values
    const [originalValues, setOriginalValues] = useState({
        redis: null,
        model: null,
        system: null
    });

    const [hasChanges, setHasChanges] = useState({
        redis: false,
        model: false,
        system: false
    });

    useEffect(() => {
        fetchAllConfigurations();
    }, []);

    const fetchAllConfigurations = async () => {
        try {
            // Fetch protection status
            const protectionResponse = await axios.get('/admin/get_protection');
            setIsProtected(protectionResponse.data.protected_api);
            setAuthToken(protectionResponse.data.auth_token);

            // Fetch Redis health and config
            const redisHealthResponse = await axios.get('/admin/redis_health');
            const redisConfig = {
                host: redisHealthResponse.data.redis_host,
                port: redisHealthResponse.data.redis_port,
                ttl: redisHealthResponse.data.ttl_seconds,
                isHealthy: redisHealthResponse.data.redis_healthy,
                keysCount: redisHealthResponse.data.context_keys_count,
            };
            setRedisConfig(redisConfig);
            setOriginalValues(prev => ({ ...prev, redis: redisConfig }));

            // Fetch model config
            const modelConfigResponse = await axios.get('/admin/model_config');
            const modelConfig = {
                timeWindowMinutes: modelConfigResponse.data.time_window_minutes,
                bucketGranularitySeconds: modelConfigResponse.data.bucket_granularity_seconds,
                minUpdateRequests: modelConfigResponse.data.min_update_requests,
            };
            setModelConfig(modelConfig);
            setOriginalValues(prev => ({ ...prev, model: modelConfig }));

            // Fetch system config
            const systemConfigResponse = await axios.get('/admin/system_config');
            const systemConfig = {
                host: systemConfigResponse.data.host,
                port: systemConfigResponse.data.port,
                debug: systemConfigResponse.data.debug,
            };
            setSystemConfig(systemConfig);
            setOriginalValues(prev => ({ ...prev, system: systemConfig }));

            setIsLoading(false);
        } catch (error) {
            console.error('Failed to fetch configurations:', error);
            setNotification({
                open: true,
                message: 'Failed to load configurations',
                severity: 'error',
            });
            setIsLoading(false);
        }
    };

    // Add effect to check for changes
    useEffect(() => {
        if (originalValues.redis) {
            const hasRedisChanges =
                redisConfig.host !== originalValues.redis.host ||
                redisConfig.port !== originalValues.redis.port ||
                redisConfig.ttl !== originalValues.redis.ttl;
            setHasChanges(prev => ({ ...prev, redis: hasRedisChanges }));
        }
    }, [redisConfig, originalValues.redis]);

    useEffect(() => {
        if (originalValues.model) {
            const hasModelChanges =
                modelConfig.timeWindowMinutes !== originalValues.model.timeWindowMinutes ||
                modelConfig.bucketGranularitySeconds !== originalValues.model.bucketGranularitySeconds ||
                modelConfig.minUpdateRequests !== originalValues.model.minUpdateRequests;
            setHasChanges(prev => ({ ...prev, model: hasModelChanges }));
        }
    }, [modelConfig, originalValues.model]);

    useEffect(() => {
        if (originalValues.system) {
            const hasSystemChanges =
                systemConfig.host !== originalValues.system.host ||
                systemConfig.port !== originalValues.system.port ||
                systemConfig.debug !== originalValues.system.debug;
            setHasChanges(prev => ({ ...prev, system: hasSystemChanges }));
        }
    }, [systemConfig, originalValues.system]);

    const handleToggleProtection = async () => {
        try {
            setIsSaving(true);
            await axios.post('/admin/set_protection', JSON.stringify(!isProtected), {
                headers: {
                    'Content-Type': 'application/json',
                },
            });
            setIsProtected(!isProtected);
            if (!isProtected) {
                setAuthToken(null);
                setJustGeneratedToken('');
            }
            setNotification({
                open: true,
                message: `API protection ${!isProtected ? 'enabled' : 'disabled'}`,
                severity: 'success',
            });
        } catch (error) {
            setNotification({
                open: true,
                message: 'Failed to update protection status',
                severity: 'error',
            });
        } finally {
            setIsSaving(false);
        }
    };

    const handleGenerateToken = async () => {
        try {
            setIsSaving(true);
            const response = await axios.post('/admin/generate_token', {});
            if (response.data?.token) {
                setJustGeneratedToken(response.data.token);
                setAuthToken(response.data.token);
                setNotification({
                    open: true,
                    message: 'New token generated successfully',
                    severity: 'success',
                });
            }
        } catch (error) {
            setNotification({
                open: true,
                message: 'Failed to generate new token',
                severity: 'error',
            });
        } finally {
            setIsSaving(false);
        }
    };

    const handleCopyToken = async () => {
        if (justGeneratedToken) {
            await navigator.clipboard.writeText(justGeneratedToken);
            setNotification({
                open: true,
                message: 'Token copied to clipboard',
                severity: 'success',
            });
        }
    };

    const handleSaveRedisConfig = async () => {
        try {
            setIsSaving(true);
            const response = await axios.post('/admin/redis_config', {
                host: redisConfig.host,
                port: parseInt(redisConfig.port),
                ttl: parseInt(redisConfig.ttl),
            });

            setOriginalValues(prev => ({ ...prev, redis: { ...redisConfig } }));
            setHasChanges(prev => ({ ...prev, redis: false }));

            if (response.data.restart_required) {
                setNotification({
                    open: true,
                    message: 'Redis configuration updated. Changes will take effect after restart.',
                    severity: 'success',
                });
            }
        } catch (error) {
            setNotification({
                open: true,
                message: 'Failed to update Redis configuration',
                severity: 'error',
            });
        } finally {
            setIsSaving(false);
        }
    };

    const handleSaveModelConfig = async () => {
        try {
            setIsSaving(true);
            await axios.post('/admin/model_config', {
                time_window_minutes: parseInt(modelConfig.timeWindowMinutes),
                bucket_granularity_seconds: parseInt(modelConfig.bucketGranularitySeconds),
                min_update_requests: parseInt(modelConfig.minUpdateRequests),
            });

            setOriginalValues(prev => ({ ...prev, model: { ...modelConfig } }));
            setHasChanges(prev => ({ ...prev, model: false }));

            setNotification({
                open: true,
                message: 'Model configuration updated successfully',
                severity: 'success',
            });
        } catch (error) {
            setNotification({
                open: true,
                message: 'Failed to update model configuration',
                severity: 'error',
            });
        } finally {
            setIsSaving(false);
        }
    };

    const handleSaveSystemConfig = async () => {
        try {
            setIsSaving(true);
            const response = await axios.post('/admin/system_config', {
                host: systemConfig.host,
                port: parseInt(systemConfig.port),
                debug: systemConfig.debug,
            });

            setOriginalValues(prev => ({ ...prev, system: { ...systemConfig } }));
            setHasChanges(prev => ({ ...prev, system: false }));

            if (response.data.restart_required) {
                setNotification({
                    open: true,
                    message: 'System configuration updated. Changes will take effect after restart.',
                    severity: 'success',
                });
            }
        } catch (error) {
            setNotification({
                open: true,
                message: 'Failed to update system configuration',
                severity: 'error',
            });
        } finally {
            setIsSaving(false);
        }
    };

    // Create a reusable SaveButton component
    const SaveButton = ({ onClick, show, disabled }) => (
        <Box
            sx={{
                display: 'flex',
                justifyContent: 'flex-end',
                marginTop: '1rem',
                height: show ? '40px' : '0px',
                opacity: show ? 1 : 0,
                transition: 'all 0.7s ease-in-out',
                overflow: 'hidden',
            }}
        >
            <Button
                variant="contained"
                onClick={onClick}
                disabled={disabled}
                sx={{
                    backgroundColor: '#3CBC84',
                    color: '#FFF',
                    fontWeight: 500,
                    fontFamily: 'Darker Grotesque',
                    fontSize: '10pt',
                    padding: '8px 16px',
                    borderRadius: '8px',
                    '&:hover': {
                        backgroundColor: '#2da872',
                    },
                    '&:disabled': {
                        backgroundColor: '#333333',
                        color: '#666666',
                    },
                }}
            >
                Save Changes
            </Button>
        </Box>
    );

    if (isLoading) {
        return (
            <Box
                sx={{
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    height: '100vh',
                }}
            >
                <CircularProgress sx={{ color: '#3CBC84' }} />
            </Box>
        );
    }

    return (
        <Box sx={{ maxWidth: '100%', margin: '0 auto' }}>
            {/* API Protection Section */}
            <Card sx={{
                backgroundColor: '#151515',
                marginBottom: '2rem',
                borderRadius: '8px',
            }}>
                <CardContent>
                    <SubTitle>API Protection</SubTitle>
                    <Box sx={{ display: 'flex', alignItems: 'center', marginBottom: '1rem' }}>
                        <Switch
                            checked={isProtected}
                            onChange={handleToggleProtection}
                            disabled={isSaving}
                            sx={{
                                '& .MuiSwitch-switchBase.Mui-checked': {
                                    color: '#3CBC84',
                                },
                                '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                                    backgroundColor: '#3CBC84',
                                },
                            }}
                        />
                        <Typography
                            sx={{
                                marginLeft: '0.5rem',
                                fontFamily: 'Darker Grotesque',
                                fontSize: '12pt',
                                color: 'white',
                            }}
                        >
                            Protect API with token
                        </Typography>
                    </Box>

                    {isProtected && (
                        <>
                            <Button
                                variant="contained"
                                onClick={handleGenerateToken}
                                disabled={isSaving}
                                sx={{
                                    backgroundColor: '#333333',
                                    color: '#FFF',
                                    fontWeight: 500,
                                    fontFamily: 'Darker Grotesque',
                                    fontSize: '10pt',
                                    padding: '8px 16px',
                                    borderRadius: '8px',
                                    marginBottom: '1rem',
                                    '&:hover': {
                                        backgroundColor: '#444444',
                                    },
                                }}
                            >
                                Generate New Token
                            </Button>

                            {justGeneratedToken && (
                                <Box
                                    sx={{
                                        backgroundColor: '#333333',
                                        padding: '1rem',
                                        borderRadius: '4px',
                                        marginBottom: '1rem',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'space-between',
                                    }}
                                >
                                    <Typography
                                        sx={{
                                            fontFamily: 'monospace',
                                            fontSize: '14px',
                                            color: 'white',
                                        }}
                                    >
                                        {justGeneratedToken}
                                    </Typography>
                                    <FaCopy
                                        style={{ marginLeft: '10px', cursor: 'pointer', color: '#C0C1C2' }}
                                        onClick={handleCopyToken}
                                    />
                                </Box>
                            )}
                        </>
                    )}
                </CardContent>
            </Card>

            {/* Redis Configuration Section */}
            <Accordion
                sx={{
                    backgroundColor: '#151515',
                    marginBottom: '1rem',
                    borderRadius: '8px !important',
                    '&:before': {
                        display: 'none',
                    },
                }}
            >
                <AccordionSummary
                    expandIcon={<FaChevronDown color="#C0C1C2" />}
                    sx={{
                        borderBottom: '1px solid #333333',
                    }}
                >
                    <Box sx={{ display: 'flex', alignItems: 'center', width: '100%' }}>
                        <SubTitle>Redis Configuration</SubTitle>
                        <Box
                            sx={{
                                marginLeft: 'auto',
                                display: 'flex',
                                alignItems: 'center',
                                marginRight: '1rem',
                            }}
                        >
                            <Typography
                                sx={{
                                    fontFamily: 'Darker Grotesque',
                                    fontSize: '12pt',
                                    color: redisConfig.isHealthy ? '#3CBC84' : '#ff4444',
                                    marginRight: '0.5rem',
                                }}
                            >
                                {redisConfig.isHealthy ? 'Healthy' : 'Unhealthy'}
                            </Typography>
                            <div
                                style={{
                                    width: '8px',
                                    height: '8px',
                                    borderRadius: '50%',
                                    backgroundColor: redisConfig.isHealthy ? '#3CBC84' : '#ff4444',
                                }}
                            />
                        </Box>
                    </Box>
                </AccordionSummary>
                <AccordionDetails>
                    <Box sx={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                        <ConfigTextField
                            label="Host"
                            value={redisConfig.host}
                            onChange={(e) => setRedisConfig(prev => ({ ...prev, host: e.target.value }))}
                            isDefault={redisConfig.host === defaultValues.redis.host}
                        />
                        <ConfigTextField
                            label="Port"
                            value={redisConfig.port}
                            onChange={(e) => setRedisConfig(prev => ({ ...prev, port: e.target.value }))}
                            isDefault={redisConfig.port === defaultValues.redis.port}
                        />
                        <ConfigTextField
                            label="TTL (seconds)"
                            value={redisConfig.ttl}
                            onChange={(e) => setRedisConfig(prev => ({ ...prev, ttl: e.target.value }))}
                            isDefault={redisConfig.ttl === defaultValues.redis.ttl}
                        />
                    </Box>

                    {redisConfig.isHealthy && (
                        <Typography
                            sx={{
                                fontFamily: 'Darker Grotesque',
                                fontSize: '12pt',
                                color: '#C0C1C2',
                                marginTop: '1rem',
                            }}
                        >
                            Active keys: {redisConfig.keysCount}
                        </Typography>
                    )}

                    <SaveButton
                        onClick={handleSaveRedisConfig}
                        show={hasChanges.redis}
                        disabled={isSaving}
                    />
                </AccordionDetails>
            </Accordion>

            {/* Model Configuration Section */}
            <Accordion
                sx={{
                    backgroundColor: '#151515',
                    marginBottom: '1rem',
                    borderRadius: '8px !important',
                    '&:before': {
                        display: 'none',
                    },
                }}
            >
                <AccordionSummary
                    expandIcon={<FaChevronDown color="#C0C1C2" />}
                    sx={{
                        borderBottom: '1px solid #333333',
                    }}
                >
                    <SubTitle>Model Configuration</SubTitle>
                </AccordionSummary>
                <AccordionDetails>
                    <Box sx={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                        <ConfigTextField
                            label="Time Window (minutes)"
                            value={modelConfig.timeWindowMinutes}
                            onChange={(e) => setModelConfig(prev => ({ ...prev, timeWindowMinutes: e.target.value }))}
                            isDefault={modelConfig.timeWindowMinutes === defaultValues.model.timeWindowMinutes}
                        />
                        <ConfigTextField
                            label="Bucket Granularity (seconds)"
                            value={modelConfig.bucketGranularitySeconds}
                            onChange={(e) => setModelConfig(prev => ({ ...prev, bucketGranularitySeconds: e.target.value }))}
                            isDefault={modelConfig.bucketGranularitySeconds === defaultValues.model.bucketGranularitySeconds}
                        />
                        <ConfigTextField
                            label="Minimum Update Requests"
                            value={modelConfig.minUpdateRequests}
                            onChange={(e) => setModelConfig(prev => ({ ...prev, minUpdateRequests: e.target.value }))}
                            isDefault={modelConfig.minUpdateRequests === defaultValues.model.minUpdateRequests}
                        />
                    </Box>

                    <SaveButton
                        onClick={handleSaveModelConfig}
                        show={hasChanges.model}
                        disabled={isSaving}
                    />
                </AccordionDetails>
            </Accordion>

            {/* System Configuration Section */}
            <Accordion
                sx={{
                    backgroundColor: '#151515',
                    marginBottom: '1rem',
                    borderRadius: '8px !important',
                    '&:before': {
                        display: 'none',
                    },
                }}
            >
                <AccordionSummary
                    expandIcon={<FaChevronDown color="#C0C1C2" />}
                    sx={{
                        borderBottom: '1px solid #333333',
                    }}
                >
                    <SubTitle>System Configuration</SubTitle>
                </AccordionSummary>
                <AccordionDetails>
                    <Box sx={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                        <ConfigTextField
                            label="Host"
                            value={systemConfig.host}
                            onChange={(e) => setSystemConfig(prev => ({ ...prev, host: e.target.value }))}
                            isDefault={systemConfig.host === defaultValues.system.host}
                        />
                        <ConfigTextField
                            label="Port"
                            value={systemConfig.port}
                            onChange={(e) => setSystemConfig(prev => ({ ...prev, port: e.target.value }))}
                            isDefault={systemConfig.port === defaultValues.system.port}
                        />
                        <Box sx={{ display: 'flex', alignItems: 'center', width: '100%' }}>
                            <Switch
                                checked={systemConfig.debug}
                                onChange={(e) => setSystemConfig(prev => ({ ...prev, debug: e.target.checked }))}
                                sx={{
                                    '& .MuiSwitch-switchBase.Mui-checked': {
                                        color: '#3CBC84',
                                    },
                                    '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                                        backgroundColor: '#3CBC84',
                                    },
                                }}
                            />
                            <Typography
                                sx={{
                                    marginLeft: '0.5rem',
                                    fontFamily: 'Darker Grotesque',
                                    fontSize: '12pt',
                                    color: 'white',
                                }}
                            >
                                Debug Mode
                            </Typography>
                        </Box>
                    </Box>

                    <SaveButton
                        onClick={handleSaveSystemConfig}
                        show={hasChanges.system}
                        disabled={isSaving}
                    />
                </AccordionDetails>
            </Accordion>

            <Snackbar
                open={notification.open}
                autoHideDuration={6000}
                onClose={() => setNotification(prev => ({ ...prev, open: false }))}
            >
                <Alert
                    onClose={() => setNotification(prev => ({ ...prev, open: false }))}
                    severity={notification.severity}
                    sx={{
                        width: '100%',
                        fontFamily: 'Darker Grotesque',
                        backgroundColor: notification.severity === 'success' ? '#3CBC84' : '#ff4444',
                        color: 'white',
                    }}
                >
                    {notification.message}
                </Alert>
            </Snackbar>
        </Box>
    );
}

export default AdminPanel; 