import React, { useState, useEffect } from 'react';
import Card from 'react-bootstrap/Card';
import Button from 'react-bootstrap/Button';
import { Collapse, DropdownButton, Dropdown } from 'react-bootstrap';
import Row from 'react-bootstrap/Row';
import Col from 'react-bootstrap/Col';
import {
    FaTrash,
    FaCopy,
    FaCircle,
    FaChevronDown,
    FaChevronUp
} from 'react-icons/fa';
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer
} from 'recharts';
import axios from 'axios';

function ModelCard({ model, onDelete, onUpdate }) {
    const [showIcon, setShowIcon] = useState(false);
    const [open, setOpen] = useState(false);

    // If global is rolled out, the "selected variant" shows that label, else "Set global variant"
    const [selectedVariant, setSelectedVariant] = useState(
        model.global_rolled_out ? model.global_variant : 'Set global variant'
    );

    useEffect(() => {
        setSelectedVariant(
            model.global_rolled_out ? model.global_variant : 'Set global variant'
        );
    }, [model.global_variant, model.global_rolled_out]);

    const copyToClipboard = () => {
        navigator.clipboard.writeText(model.model_id);
    };

    const handleVariantSelect = async (variantLabel) => {
        // The user can pick "Remove override" or a variant label. We'll send that to the server.
        if (variantLabel === 'Remove override') {
            // Call the clear_global_variant endpoint
            try {
                await axios.post(
                    `/api/clear_global_variant/${model.model_id}`
                );
                if (onUpdate) {
                    onUpdate();
                }
            } catch (error) {
                console.error(error);
            }
        } else {
            setSelectedVariant(variantLabel);
            try {
                // Post to rollout_global_variant with { variant: variantLabel }
                // The server will interpret it as a string if it doesn't parse as int
                await axios.post(
                    `/api/rollout_global_variant/${model.model_id}`,
                    { variant: variantLabel }
                );
                if (onUpdate) {
                    onUpdate();
                }
            } catch (error) {
                console.error(error);
            }
        }
    };

    const formatRequestTrailData = () => {
        return model.request_trail.map(entry => ({
            time: new Date(entry.time_bucket).getTime(),
            ...entry.frequency
        }));
    };

    const requestData = model.prediction_requests === 0 ? [] : formatRequestTrailData();

    const formatExploitationData = () => {
        return model.exploitation_status.map(entry => ({
            n: entry.n,
            exploitation: entry.exploitation
        }));
    };

    const exploitationData = model.prediction_requests === 0 ? [] : formatExploitationData();

    const colors = ['#8884d8', '#82ca9d', '#ffc658', '#ff7300'];

    // If the model has a global override, show a different dropdown title
    const dropdownTitle = model.global_rolled_out
        ? `Override: ${model.global_variant}`
        : 'Override';

    // Convert the dictionary of variants (e.g. {0:'red',1:'blue'}) into an array of [internalKey, label] pairs
    const variantEntries = Object.entries(model.variants || {});
    // e.g. [["0", "red"], ["1","blue"]]

    // Build a string to display in the card: "0:red, 1:blue"
    const variantLabelsString = variantEntries
        .map(([k, v]) => `${v}`)
        .join(' | ');

    return (
        <Card
            className="mb-3 shadow-sm"
            style={{ backgroundColor: '#151515', color: '#C0C1C2', position: 'relative' }}
        >
            <Card.Body>
                <Card.Title
                    as="h5"
                    style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center'
                    }}
                >
                    {/* Left side content */}
                    <div
                        onMouseEnter={() => setShowIcon(true)}
                        onMouseLeave={() => setShowIcon(false)}
                        style={{ display: 'flex', alignItems: 'center' }}
                    >
                        <strong style={{ color: '#3CBC84', fontSize: '1rem' }}>
                            {model.name}
                        </strong>
                        {model.active ? (
                            <FaCircle
                                style={{
                                    color: '#32a854',
                                    marginLeft: '10px',
                                    fontSize: '0.8rem'
                                }}
                            />
                        ) : (
                            <FaCircle
                                style={{
                                    color: '#d93025',
                                    marginLeft: '10px',
                                    fontSize: '0.8rem'
                                }}
                            />
                        )}
                        {model.global_rolled_out ? (
                            <Card.Text
                                style={{
                                    color: '#d93025',
                                    marginLeft: '5px',
                                    fontSize: '0.7rem'
                                }}
                            >
                                Override Enabled
                            </Card.Text>
                        ) : model.active && model.update_requests > 0 ? (
                            <Card.Text
                                style={{
                                    color: '#32a854',
                                    marginLeft: '5px',
                                    fontSize: '0.7rem'
                                }}
                            >
                                Optimizing
                            </Card.Text>
                        ) : model.active && model.update_requests === 0 ? (
                            <Card.Text
                                style={{
                                    color: '#32a854',
                                    marginLeft: '5px',
                                    fontSize: '0.7rem'
                                }}
                            >
                                Ready to receive requests
                            </Card.Text>
                        ) : null}
                    </div>
                    {/* Right side content */}
                    <div style={{ display: 'flex', alignItems: 'center' }}>
                        <DropdownButton
                            id={`dropdown-variant-${model.model_id}`}
                            title={<span style={{ fontSize: '0.7rem' }}>{dropdownTitle}</span>}
                            variant="dark"
                            data-bs-theme="dark"
                            onSelect={handleVariantSelect}
                            bg="dark"
                            size="sm"
                            style={{ fontSize: '0.7rem' }}
                        >
                            {variantEntries.map(([internalKey, label]) => (
                                <Dropdown.Item
                                    eventKey={label} // We pass the user-friendly label as the eventKey
                                    key={internalKey}
                                    style={{ fontSize: '0.7rem' }}
                                >
                                    {label}
                                </Dropdown.Item>
                            ))}
                            {model.global_rolled_out && (
                                <>
                                    <Dropdown.Divider />
                                    <Dropdown.Item
                                        eventKey="Remove override"
                                        style={{ color: 'red', fontSize: '0.7rem' }}
                                    >
                                        Remove
                                    </Dropdown.Item>
                                </>
                            )}
                        </DropdownButton>

                        <Button
                            variant="outline-danger"
                            onClick={() => onDelete(model.model_id)}
                            className="ms-2"
                            size="sm"
                        >
                            <FaTrash />
                        </Button>
                    </div>
                </Card.Title>

                <Card.Text
                    onMouseEnter={() => setShowIcon(true)}
                    onMouseLeave={() => setShowIcon(false)}
                >
                    <strong
                        style={{
                            fontFamily: 'Darker Grotesque',
                            fontWeight: 700,
                            fontSize: '0.8rem'
                        }}
                    >
                        ID
                    </strong>{' '}
                    <span
                        style={{
                            marginLeft: '10px',
                            fontFamily: 'monospace',
                            fontSize: '0.8rem',
                            color: '#787878'
                        }}
                    >
                        {model.model_id}
                    </span>
                    {showIcon && (
                        <FaCopy
                            style={{ marginLeft: '10px', cursor: 'pointer', color: '#C0C1C2' }}
                            onClick={copyToClipboard}
                        />
                    )}
                    <br />
                    <strong
                        style={{
                            fontFamily: 'Darker Grotesque',
                            fontWeight: 700,
                            fontSize: '0.8rem'
                        }}
                    >
                        Variants
                    </strong>{' '}
                    <div style={{ marginLeft: '5px', display: 'inline-flex', flexWrap: 'wrap', gap: '5px' }}>
                        {variantEntries.map(([key, label]) => (
                            <span
                                key={key}
                                style={{
                                    background: '#333333',
                                    color: '#fff',
                                    padding: '0px 10px',
                                    borderRadius: '5px',
                                    fontSize: '0.8rem',
                                    fontFamily: 'monospace'
                                }}
                            >
                                {label}
                            </span>
                        ))}
                    </div>
                    <br />
                    <strong
                        style={{
                            fontFamily: 'Darker Grotesque',
                            fontWeight: 700,
                            fontSize: '0.8rem'
                        }}
                    >
                        Created
                    </strong>{' '}
                    <span
                        style={{
                            marginLeft: '10px',
                            fontSize: '0.8rem',
                            fontFamily: 'monospace',
                            color: '#787878'
                        }}
                    >
                        {new Date(model.created_at).toLocaleString()}
                    </span>
                    <br />
                    <strong
                        style={{
                            fontFamily: 'Darker Grotesque',
                            fontWeight: 700,
                            fontSize: '0.8rem'
                        }}
                    >
                        Update URL
                    </strong>{' '}
                    <span
                        style={{
                            marginLeft: '10px',
                            fontSize: '0.8rem',
                            fontFamily: 'monospace',
                            color: '#787878'
                        }}
                    >
                        {model.URL}
                    </span>
                </Card.Text>

                <Row>
                    <Col md={8}>
                        <Card.Text>
                            <strong
                                style={{
                                    fontFamily: 'Darker Grotesque',
                                    fontWeight: 700,
                                    fontSize: '0.8rem'
                                }}
                            >
                                Last Update Request
                            </strong>{' '}
                            <span
                                style={{
                                    fontFamily: 'monospace',
                                    fontSize: '0.8rem',
                                    color: '#787878'
                                }}
                            >
                                {model.latest_update_request
                                    ? new Date(model.latest_update_request).toLocaleString()
                                    : '—'}
                            </span>
                            <br />
                            <strong
                                style={{
                                    fontFamily: 'Darker Grotesque',
                                    fontWeight: 700,
                                    fontSize: '0.8rem'
                                }}
                            >
                                Last Prediction Request
                            </strong>{' '}
                            <span
                                style={{
                                    fontFamily: 'monospace',
                                    fontSize: '0.8rem',
                                    color: '#787878'
                                }}
                            >
                                {model.latest_prediction_request
                                    ? new Date(model.latest_prediction_request).toLocaleString()
                                    : '—'}
                            </span>
                        </Card.Text>
                    </Col>
                </Row>

                <Button
                    onClick={() => setOpen(!open)}
                    aria-controls="example-collapse-text"
                    aria-expanded={open}
                    style={{
                        background: 'none',
                        color: '#C0C1C2',
                        border: 'none',
                        borderBottom: '0.5px solid',
                        width: '100%',
                        textAlign: 'right',
                        padding: '0px',
                        boxShadow: 'none',
                        borderRadius: 0
                    }}
                >
                    {open ? <FaChevronUp /> : <FaChevronDown />}
                </Button>
                <Collapse in={open}>
                    <div id="example-collapse-text" style={{ paddingTop: '10px' }}>
                        <Card.Text>
                            <strong
                                style={{
                                    fontFamily: 'Darker Grotesque',
                                    fontWeight: 700,
                                    fontSize: '0.8rem'
                                }}
                            >
                                Prediction Requests
                            </strong>{' '}
                            <span style={{ fontSize: '0.8rem' }}>
                                {model.prediction_requests}
                            </span>
                            <br />
                            <strong
                                style={{
                                    fontFamily: 'Darker Grotesque',
                                    fontWeight: 700,
                                    fontSize: '0.8rem'
                                }}
                            >
                                Update Requests
                            </strong>{' '}
                            <span style={{ fontSize: '0.8rem' }}>
                                {model.update_requests}
                            </span>
                            <br />
                            <strong
                                style={{
                                    fontFamily: 'Darker Grotesque',
                                    fontWeight: 700,
                                    fontSize: '0.8rem'
                                }}
                            >
                                Prediction Ratios:
                            </strong>{' '}
                            <span style={{ fontSize: '0.8rem' }}>
                                {Object.entries(model.prediction_ratio)
                                    .map(([k, v]) => `${k} → ${(v * 100).toFixed(0)}%`)
                                    .join('   | ')}
                            </span>
                            <br />
                            <strong
                                style={{
                                    fontFamily: 'Darker Grotesque',
                                    fontWeight: 700,
                                    fontSize: '0.8rem'
                                }}
                            >
                                Optimization Status:
                            </strong>{' '}
                            <span style={{ fontSize: '0.8rem' }}>
                                {`${model.exploit_explore_ratio.exploitation}%`}
                            </span>
                        </Card.Text>

                        <ul>
                            {model.features.map((feature, index) => (
                                <li
                                    key={index}
                                    style={{
                                        fontFamily: 'monospace',
                                        fontSize: '0.8rem',
                                        color: '#787878'
                                    }}
                                >
                                    {feature}
                                </li>
                            ))}
                        </ul>

                        <Card.Text>
                            <strong
                                style={{
                                    fontFamily: 'Darker Grotesque',
                                    fontWeight: 700,
                                    fontSize: '0.8rem'
                                }}
                            >
                                Total Reward:
                            </strong>{' '}
                            <span style={{ fontSize: '0.8rem' }}>
                                {`${Math.round(model.reward_summary.total_reward)} (${model.reward_summary.relative_increase}% uplift over random test)`}
                            </span>
                        </Card.Text>

                        <Row>
                            <Col md={6} style={{ position: 'relative' }}>
                                {/* Line chart for request trail */}
                                <div>
                                    <div style={{ textAlign: 'center', marginBottom: '10px' }}>
                                        <strong
                                            style={{
                                                fontFamily: 'Darker Grotesque',
                                                fontWeight: 200,
                                                fontSize: '0.7rem'
                                            }}
                                        >
                                            Prediction Requests (RPM)
                                        </strong>
                                    </div>
                                    <ResponsiveContainer width="100%" height={200}>
                                        <LineChart
                                            data={requestData}
                                            margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
                                        >
                                            <XAxis
                                                dataKey="time"
                                                domain={['dataMin', 'dataMax']}
                                                type="number"
                                                fontSize="0.7rem"
                                                tickFormatter={(time) =>
                                                    new Date(time).toLocaleTimeString([], {
                                                        hour: '2-digit',
                                                        minute: '2-digit'
                                                    })
                                                }
                                            />
                                            <YAxis fontSize="0.7rem" />
                                            <CartesianGrid stroke="#cccc" strokeDasharray="1 5" />
                                            <Tooltip
                                                labelFormatter={(label) =>
                                                    new Date(label).toLocaleString()
                                                }
                                            />
                                            <Legend wrapperStyle={{ fontSize: '0.7rem' }} />
                                            {variantEntries.map(([internalKey, label], index) => (
                                                <Line
                                                    key={internalKey}
                                                    type="monotone"
                                                    dataKey={label}
                                                    stroke={colors[index % colors.length]}
                                                />
                                            ))}
                                        </LineChart>
                                    </ResponsiveContainer>
                                </div>

                                {model.prediction_requests === 0 && (
                                    <div
                                        style={{
                                            position: 'absolute',
                                            top: 0,
                                            left: 0,
                                            right: 0,
                                            bottom: '40%',
                                            display: 'flex',
                                            justifyContent: 'center',
                                            alignItems: 'center',
                                            color: '#787878',
                                            fontSize: '0.7rem'
                                        }}
                                    >
                                        No Prediction Requests
                                    </div>
                                )}
                            </Col>
                            <Col md={6} style={{ position: 'relative' }}>
                                {/* Line chart for exploitation status */}
                                <div>
                                    <div style={{ textAlign: 'center', marginBottom: '10px' }}>
                                        <strong
                                            style={{
                                                fontFamily: 'Darker Grotesque',
                                                fontWeight: 200,
                                                fontSize: '0.7rem'
                                            }}
                                        >
                                            Exploitation Rate
                                        </strong>
                                    </div>
                                    <ResponsiveContainer width="100%" height={200}>
                                        <LineChart
                                            data={exploitationData}
                                            margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
                                        >
                                            <XAxis
                                                dataKey="n"
                                                type="number"
                                                tickFormatter={(n) => `N=${n}`}
                                                fontSize="0.7rem"
                                            />
                                            <YAxis
                                                domain={[0, 100]}
                                                tickFormatter={(tick) => `${tick}%`}
                                                ticks={[0, 50, 100]}
                                                fontSize="0.7rem"
                                            />
                                            <CartesianGrid stroke="#cccc" strokeDasharray="1 5" />
                                            <Tooltip />
                                            <Legend wrapperStyle={{ fontSize: '0.7rem' }} />
                                            <Line
                                                type="monotone"
                                                dataKey="exploitation"
                                                stroke="#ff7300"
                                            />
                                        </LineChart>
                                    </ResponsiveContainer>
                                </div>
                                {model.prediction_requests === 0 && (
                                    <div
                                        style={{
                                            position: 'absolute',
                                            top: 0,
                                            left: 0,
                                            right: 0,
                                            bottom: '40%',
                                            display: 'flex',
                                            justifyContent: 'center',
                                            alignItems: 'center',
                                            color: '#787878',
                                            fontSize: '0.7rem'
                                        }}
                                    >
                                        No Prediction Requests
                                    </div>
                                )}
                            </Col>
                        </Row>
                    </div>
                </Collapse>
            </Card.Body>
        </Card>
    );
}

export default ModelCard;
