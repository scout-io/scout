import React, { useEffect, useState } from 'react';
import axios from 'axios';
import ModelCard from './ModelCard';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';
import { createTheme, ThemeProvider } from '@mui/material/styles';
import Fade from '@mui/material/Fade';

// --- Added MUI Dialog imports for the delete confirmation modal ---
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';

const theme = createTheme({
    typography: {
        fontFamily: 'Darker Grotesque, sans-serif',
        button: {
            textTransform: 'none',
        },
    },
    palette: {
        mode: 'dark',
    },
});

function ModelList({ currentScreen }) {
    const [models, setModels] = useState([]);
    const [showForm, setShowForm] = useState(false);

    // Number of variant arms
    const [variants, setVariants] = useState(2);

    // Name of the test/model
    const [name, setName] = useState('');

    // For each variant (0 to variants-1), we store a label (string).
    const [variantLabels, setVariantLabels] = useState([]);

    // Search term for filtering
    const [searchTerm, setSearchTerm] = useState('');

    // --- State for delete confirmation dialog ---
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [modelIdToDelete, setModelIdToDelete] = useState(null);

    useEffect(() => {
        fetchModels();
    }, []);

    // Whenever the user changes the 'variants' number, re-initialize the variantLabels array
    useEffect(() => {
        const newVariantLabels = [];
        for (let i = 0; i < variants; i++) {
            newVariantLabels.push('');
        }
        setVariantLabels(newVariantLabels);
    }, [variants]);

    const fetchModels = async () => {
        // GET /models might be public, but if there's a token let's pass it anyway
        const token = localStorage.getItem('authToken');
        const headers = token ? { Authorization: `Bearer ${token}` } : {};

        try {
            const response = await axios.get('/api/models', { headers });
            // Sort models so that active ones are first, then by creation date descending
            const sortedModels = response.data.sort((a, b) => {
                if (a.active === b.active) {
                    return new Date(b.created_at) - new Date(a.created_at);
                }
                return a.active ? -1 : 1;
            });
            setModels(sortedModels);
        } catch (error) {
            console.error(error);
        }
    };

    // Update a single variant's label in the variantLabels array
    const handleVariantLabelChange = (index, value) => {
        const newLabels = [...variantLabels];
        newLabels[index] = value;
        setVariantLabels(newLabels);
    };

    const handleSubmit = async (event) => {
        event.preventDefault();
        // Construct the variants dictionary
        // Keys are 0..(variants-1); values are whatever user typed or fallback to index
        const variantDict = {};
        for (let i = 0; i < variants; i++) {
            variantDict[i] = variantLabels[i] || i;
        }

        const token = localStorage.getItem('authToken');
        const headers = token ? { Authorization: `Bearer ${token}` } : {};

        try {
            // POST request with the new format: { variants: {0:...,1:...}, name: '...' }
            await axios.post(
                '/api/create_model',
                {
                    variants: variantDict,
                    name: name,
                },
                { headers }
            );
            fetchModels();
            setShowForm(false);
            setName('');
            setVariants(2);
        } catch (error) {
            console.error(error);
        }
    };

    // --- Actual Axios delete call (will be triggered after user confirms) ---
    const handleDelete = async (modelId) => {
        const token = localStorage.getItem('authToken');
        const headers = token ? { Authorization: `Bearer ${token}` } : {};

        try {
            await axios.post(`/api/delete_model/${modelId}`, {}, { headers });
            fetchModels();
        } catch (error) {
            console.error(error);
        }
    };

    // --- Open the dialog, storing which model we want to delete ---
    const handleOpenDeleteDialog = (modelId) => {
        setModelIdToDelete(modelId);
        setDeleteDialogOpen(true);
    };

    // --- Close the dialog without deleting ---
    const handleCloseDeleteDialog = () => {
        setDeleteDialogOpen(false);
        setModelIdToDelete(null);
    };

    // --- If user confirms, call handleDelete, then close the dialog ---
    const handleConfirmDelete = async () => {
        if (modelIdToDelete) {
            await handleDelete(modelIdToDelete);
        }
        handleCloseDeleteDialog();
    };

    // Filter models by name OR model_id, case-insensitive
    const filteredModels = models.filter((model) => {
        const lowerSearchTerm = searchTerm.toLowerCase();
        const modelName = model.name?.toLowerCase() || '';
        const modelId = model.model_id?.toLowerCase() || '';
        return modelName.includes(lowerSearchTerm) || modelId.includes(lowerSearchTerm);
    });

    return (
        <ThemeProvider theme={theme}>
            <Box>
                {currentScreen === 'Tests' && (
                    <Box>
                        {/* When form is collapsed, put "Create Test" and Search on the same row */}
                        {!showForm && (
                            <Box
                                sx={{
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'center',
                                    mb: 3,
                                }}
                            >
                                <Button
                                    variant="contained"
                                    onClick={() => setShowForm(true)}
                                    sx={{
                                        backgroundColor: '#1D1D1D',
                                        color: '#FFF',
                                        fontFamily: 'Darker Grotesque',
                                        fontWeight: 500,
                                        fontSize: '12pt',
                                        borderRadius: '5px',
                                        padding: '7px 15px',
                                        boxShadow: 0,
                                        '&:hover': {
                                            backgroundColor: '#333333',
                                        },
                                    }}
                                >
                                    Create Test ＋
                                </Button>

                                {/* Search bar (collapsed state) */}
                                <TextField
                                    label="⌕"
                                    variant="outlined"
                                    size='small'
                                    value={searchTerm}
                                    onChange={(e) => setSearchTerm(e.target.value)}
                                    sx={{
                                        // Target the root of the outlined input
                                        '& .MuiOutlinedInput-root': {
                                            // Round corners on the container
                                            borderRadius: '8px',
                                            // Apply a background color to match the same container
                                            backgroundColor: '#333333',
                                            // Remove the outline border
                                            '& fieldset': {
                                                border: 'none',
                                            },
                                            '&:hover fieldset': {
                                                border: 'none',
                                            },
                                            '&.Mui-focused fieldset': {
                                                border: 'none',
                                            },
                                        },

                                        // Ensure the notched outline also has the same borderRadius
                                        '& .MuiOutlinedInput-notchedOutline': {
                                            borderRadius: '8px',
                                            border: 'none',
                                        },

                                        // (Optional) label styling
                                        '& .MuiInputLabel-root': {
                                            color: '#FFF',
                                        },
                                        '& .MuiInputLabel-root.Mui-focused': {
                                            color: '#FFF',
                                        },
                                    }}
                                />
                            </Box>
                        )}

                        {/* When form is expanded, put the search bar below the card */}
                        {showForm && (
                            <Box sx={{ mb: 3 }}>
                                <Button
                                    variant="contained"
                                    onClick={() => setShowForm(false)}
                                    sx={{
                                        mb: 2,
                                        backgroundColor: '#1D1D1D',
                                        color: '#FFF',
                                        fontFamily: 'Darker Grotesque',
                                        fontWeight: 500,
                                        fontSize: '12pt',
                                        borderRadius: '5px',
                                        padding: '7px 15px',
                                        boxShadow: 0,
                                        '&:hover': {
                                            backgroundColor: '#333333',
                                        },
                                    }}
                                >
                                    Cancel
                                </Button>

                                <Card
                                    sx={{
                                        mb: 2,
                                        p: 0,
                                        borderRadius: 2,
                                        boxShadow: 3,
                                        backgroundColor: '#1D1D1D',
                                        color: '#FFF',
                                    }}
                                >
                                    <CardContent>
                                        <form onSubmit={handleSubmit}>
                                            <Grid container spacing={2} alignItems="center">
                                                {/* Model Name */}
                                                <Grid item xs={12} sm={6}>
                                                    <TextField
                                                        label="Test Name"
                                                        fullWidth
                                                        required
                                                        value={name}
                                                        onChange={(e) => setName(e.target.value)}
                                                        variant="outlined"
                                                        sx={{
                                                            mb: 2,
                                                            backgroundColor: '#333333',
                                                            borderRadius: '8px',
                                                            '& .MuiOutlinedInput-root': {
                                                                color: '#FFF',
                                                                '& fieldset': {
                                                                    borderColor: '#444',
                                                                },
                                                                '&:hover fieldset': {
                                                                    borderColor: '#555',
                                                                },
                                                                '&.Mui-focused fieldset': {
                                                                    borderColor: '#FFF',
                                                                },
                                                            },
                                                            '& .MuiInputLabel-root': {
                                                                color: '#FFF',
                                                            },
                                                            '& .MuiInputLabel-root.Mui-focused': {
                                                                color: '#FFF',
                                                            },
                                                        }}
                                                    />
                                                </Grid>

                                                {/* Number of variants */}
                                                <Grid item xs={12} sm={6}>
                                                    <TextField
                                                        label="Number of Variants"
                                                        type="number"
                                                        fullWidth
                                                        value={variants}
                                                        onChange={(e) => {
                                                            const num = parseInt(e.target.value, 10);
                                                            setVariants(num > 0 ? num : 1);
                                                        }}
                                                        variant="outlined"
                                                        InputLabelProps={{ style: { fontSize: 16 } }}
                                                        sx={{
                                                            mb: 2,
                                                            backgroundColor: '#333333',
                                                            borderRadius: '8px',
                                                            '& .MuiOutlinedInput-root': {
                                                                color: '#FFF',
                                                                '& fieldset': {
                                                                    borderColor: '#444',
                                                                },
                                                                '&:hover fieldset': {
                                                                    borderColor: '#555',
                                                                },
                                                                '&.Mui-focused fieldset': {
                                                                    borderColor: '#FFF',
                                                                },
                                                            },
                                                            '& .MuiInputLabel-root': {
                                                                color: '#FFF',
                                                            },
                                                            '& .MuiInputLabel-root.Mui-focused': {
                                                                color: '#FFF',
                                                            },
                                                        }}
                                                    />
                                                </Grid>
                                            </Grid>

                                            {/* Variant labels (one text field per variant) */}
                                            <Fade in={true} timeout={500}>
                                                <Grid container spacing={2} sx={{ mt: 1 }}>
                                                    {Array.from({ length: variants }, (_, i) => (
                                                        <Grid item xs={12} key={i}>
                                                            <TextField
                                                                label={`Variant ${i + 1} Label`}
                                                                fullWidth
                                                                value={variantLabels[i] ?? ''}
                                                                onChange={(e) =>
                                                                    handleVariantLabelChange(i, e.target.value)
                                                                }
                                                                variant="outlined"
                                                                sx={{
                                                                    backgroundColor: '#333333',
                                                                    borderRadius: '8px',
                                                                    '& .MuiOutlinedInput-root': {
                                                                        color: '#FFF',
                                                                        '& fieldset': {
                                                                            borderColor: '#444',
                                                                        },
                                                                        '&:hover fieldset': {
                                                                            borderColor: '#555',
                                                                        },
                                                                        '&.Mui-focused fieldset': {
                                                                            borderColor: '#FFF',
                                                                        },
                                                                    },
                                                                    '& .MuiInputLabel-root': {
                                                                        color: '#FFF',
                                                                    },
                                                                    '& .MuiInputLabel-root.Mui-focused': {
                                                                        color: '#FFF',
                                                                    },
                                                                }}
                                                            />
                                                        </Grid>
                                                    ))}
                                                </Grid>
                                            </Fade>

                                            <Grid container spacing={2} sx={{ mt: 2 }}>
                                                <Grid item xs={12}>
                                                    <Button
                                                        variant="contained"
                                                        type="submit"
                                                        sx={{
                                                            backgroundColor: '#333333',
                                                            color: '#FFF',
                                                            fontWeight: 500,
                                                            fontSize: '12pt',
                                                            padding: '10px 20px',
                                                            borderRadius: '8px',
                                                            width: '100%',
                                                            '&:hover': {
                                                                backgroundColor: '#444444',
                                                            },
                                                        }}
                                                    >
                                                        Generate Endpoint
                                                    </Button>
                                                </Grid>
                                            </Grid>
                                        </form>
                                    </CardContent>
                                </Card>

                                {/* Search bar (expanded state, placed below the card) */}
                                <Box
                                    sx={{
                                        display: 'flex',
                                        justifyContent: 'flex-end',
                                    }}
                                >
                                    <TextField
                                        label="⌕"
                                        variant="outlined"
                                        size='small'
                                        value={searchTerm}
                                        onChange={(e) => setSearchTerm(e.target.value)}
                                        sx={{
                                            // Target the root of the outlined input
                                            '& .MuiOutlinedInput-root': {
                                                // Round corners on the container
                                                borderRadius: '8px',
                                                // Apply a background color to match the same container
                                                backgroundColor: '#333333',
                                                // Remove the outline border
                                                '& fieldset': {
                                                    border: 'none',
                                                },
                                                '&:hover fieldset': {
                                                    border: 'none',
                                                },
                                                '&.Mui-focused fieldset': {
                                                    border: 'none',
                                                },
                                            },

                                            // Ensure the notched outline also has the same borderRadius
                                            '& .MuiOutlinedInput-notchedOutline': {
                                                borderRadius: '8px',
                                                border: 'none',
                                            },

                                            // (Optional) label styling
                                            '& .MuiInputLabel-root': {
                                                color: '#FFF',
                                            },
                                            '& .MuiInputLabel-root.Mui-focused': {
                                                color: '#FFF',
                                            },
                                        }}
                                    />
                                </Box>
                            </Box>
                        )}

                        {/* Render filtered models */}
                        {filteredModels.map((model) => (
                            <ModelCard
                                key={model.model_id}
                                model={model}
                                // Instead of calling handleDelete directly, we open the confirmation dialog
                                onDelete={handleOpenDeleteDialog}
                                onUpdate={fetchModels}
                            />
                        ))}
                    </Box>
                )}
            </Box>

            {/* --- Delete Confirmation Modal (MUI Dialog) --- */}
            <Dialog
                open={deleteDialogOpen}
                onClose={handleCloseDeleteDialog}
                PaperProps={{
                    style: {
                        backgroundColor: '#1D1D1D',
                        color: '#FFF',
                        borderRadius: '8px',
                    },
                }}
            >
                <DialogTitle sx={{ fontFamily: 'Darker Grotesque, sans-serif' }}>
                    Confirm Deletion
                </DialogTitle>
                <DialogContent>
                    <DialogContentText sx={{ color: '#FFF' }}>
                        Are you sure you want to delete this model? This cannot be undone.
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={handleCloseDeleteDialog} sx={{ color: '#FFF' }}>
                        Cancel
                    </Button>
                    <Button
                        onClick={handleConfirmDelete}
                        sx={{
                            backgroundColor: '#333333',
                            color: '#FFF',
                            '&:hover': {
                                backgroundColor: '#444444',
                            },
                        }}
                    >
                        Delete
                    </Button>
                </DialogActions>
            </Dialog>
        </ThemeProvider>
    );
}

export default ModelList;
