import React from 'react'
import produce from 'immer'
import {
    Spinbox,
    Button,
    timeLimitString,
    memLimitString } from './components'
import { Link, useParams } from "react-router-dom";
import {getBrowserVisibilityProp, getIsDocumentHidden} from './visibility'
import SyntaxHighlighter from 'react-syntax-highlighter';
import { docco } from 'react-syntax-highlighter/dist/esm/styles/hljs';
import Collapsible from 'react-collapsible';

class DetailProxy {
    constructor(endpoint) {
        this.endpoint = endpoint;
        this.cache = {}
        this.enabled = true;
        window.addEventListener(getBrowserVisibilityProp(), this.onWindowFocus);
    }

    onWindowFocus = () => {
        this.enabled = !getIsDocumentHidden();
    }

    async get(suiteId) {
        if (suiteId in this.cache)
            return this.cache[suiteId];
        let response = await fetch(this.endpoint + "/" + suiteId.toString())
        if (!response.ok) {
            throw new Error(response.statusText);
        }
        if (response.status !== 200) {
            let text = await response.text();
            throw new Error(`Response: ${response.status}: ${text}`);
        }
        let suite = await response.json();
        this.cache[suiteId] = suite;
        return suite;
    }

    requestUpdate(suiteId) {
        if (this.enabled) {
            delete this.cache[suiteId];
        }
        return this.get(suiteId)
    }
}

var SUITE_PROXY = new DetailProxy("/api/suites");
var TASK_PROXY = new DetailProxy("/api/tasks");

class ExpandableTableRow extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            expanded: false
        }
    }

    handleClick = (e) => {
        e.preventDefault();
        this.setState(produce(this.state, draft => {
            draft.expanded = !draft.expanded;
        }));
    }

    render() {
        let expandableContent = <></>
        let className = this.props.className ? this.props.className : "";
        if (this.state.expanded && this.props.expandableContent) {
            expandableContent = <tr>
                    <td colSpan={this.props.children.length}>
                        {this.props.expandableContent}
                    </td>
                </tr>;
        }
        if (this.props.expandableContent)
            className += " cursor-pointer";
        return <>
            <tr className={className} onClick={this.handleClick}>
                {this.props.children}
            </tr>
            {expandableContent}
        </>
    }
}

function BenchamarkEnv(props) {
    let env = props.env;
    let params = [
        ["CPU core limit:", env.cpuLimit],
        ["Wall-clock timeout:", timeLimitString(env.wallClockTimeLimit)],
        ["CPU timeout:", timeLimitString(env.cpuTimeLimit)],
        ["Memory limit:", memLimitString(env.memoryLimit)]
    ];

    return <>
        <table className="w-full">
            <tbody>
                {
                    params.map((row, i) => {
                        return <tr key={i}>
                            <td>
                                {row[0]}
                            </td>
                            <td>
                                {row[1]}
                            </td>
                        </tr>
                    })
                }
                {
                    Object.keys(env.params).map((keyName, i) => {
                        return <tr key={i}>
                            <td>
                                { i === 0 ? "Build arguments:" : ""}
                            </td>
                            <td>
                                {keyName}={env.params[keyName]}
                            </td>
                        </tr>
                    })
                }
            </tbody>
        </table>
        <Collapsible
                trigger="Open environment definition&nbsp;∨"
                triggerWhenOpen="Close environment definition&nbsp;∧"
                transitionTime={100}
                triggerClassName="cursor-pointer underline text-blue-500 hover:text-blue-800"
                triggerOpenedClassName="cursor-pointer underline text-blue-500 hover:text-blue-800">
            <SyntaxHighlighter
                    language="dockerfile"
                    style={docco}
                    showLineNumbers={true}
                    className="text-sm">
                {env.dockerfile}
            </SyntaxHighlighter>
        </Collapsible>
    </>
}

function SuiteStatistics(props) {
    let suite = props.suite;
    return <div className="w-full">
        <a href={"/api/suites/" + suite.id + "/results"} target="_blank" rel="noreferrer">
            <Button className="w-full">
                Download JSON summary of suite: {suite.id}
            </Button>
        </a>
    </div>
}

class EntityDetail extends React.Component {
    constructor(proxy, props) {
        super(props);
        this.proxy = proxy;
        this.state = {};
    }

    componentDidMount() {
        this.handleUpdate(this.proxy.get(this.props.entityId));
        this.updateTimer = setInterval(this.update, 5000);
    }

    componentWillUnmount() {
        clearInterval(this.updateTimer);
    }

    handleUpdate = response => {
        response
            .then(entity => {
                console.log(entity);
                this.setState({"entity": entity, "message": undefined});
            })
            .catch(e => {
                this.setState({"message": e.message});
            });
    }

    update = () => {
        this.handleUpdate(this.proxy.requestUpdate(this.props.entityId))
    }

    render() {
        if (!(this.state.message || this.state.entity)) {
            return <Spinbox/>
        }
        if (this.state.message) {
            return <p>{this.state.message}</p>
        }
        if (this.state.entity.id === undefined) {
            return <p>Invalid state</p>
        }
        return this.renderEntity(this.state.entity);
    }
}

function TaskDetailField(props) {
    let content = props.content;
    if (!props.content)
        content = "";
    return <Collapsible
            trigger={"Open " + props.what + "∨"}
            triggerWhenOpen={"Close " + props.what + "∧"}
            transitionTime={100}
            triggerClassName="cursor-pointer underline text-blue-500 hover:text-blue-800"
            triggerOpenedClassName="cursor-pointer underline text-blue-500 hover:text-blue-800">
        <SyntaxHighlighter
                language={props.language}
                style={docco}
                showLineNumbers={true}
                className="text-sm">
            {content}
        </SyntaxHighlighter>
    </Collapsible>
}

class TaskDetail extends EntityDetail {
    constructor(props) {
        super(TASK_PROXY, props);
    }

    renderEntity(task) {
        if (task.stats === null)
            task.stats = {};
        return <div className="w-full flex flex-wrap p-3 pl-8 border-black border-l-4">
            <div className="w-full md:w-1/2">
                <p>Exit code: {task.exitcode}</p>
                <p>Wall-clock time: {timeLimitString(task.stats.wallTime / 1000000)}</p>
                <p>Cpu-clock time: {timeLimitString(task.stats.cpuTime / 1000000)}</p>
                <p>Exit code: {task.exitcode}</p>
            </div>
            <div className="w-full md:w-1/2">
                <a href={"/api/tasks/" + task.id} target="_blank" rel="noreferrer">
                    <Button className="w-full">
                        Download JSON summary of task {task.id}
                    </Button>
                </a>
            </div>
            <div className="w-full">
                <TaskDetailField
                    what="standard output"
                    content={task.output}/>
                <TaskDetailField
                    what="statistics"
                    content={JSON.stringify(task.stats, null, 4)}
                    language="json"/>
                <TaskDetailField
                    what="benchmark artifact"
                    content={JSON.stringify(task.result, null, 4)}
                    language="json"/>
            </div>
        </div>;
    }
}

function taskRowClass(task, index) {
    let colorCoding = {
        "created": ["gray", 100, 200],
        "pending": ["gray", 100, 200],
        "assigned": ["blue", 100, 200],
        "success": ["green", 100, 200],
        "fail": ["red", 100, 200]
    };
    let state = task.state;
    if (state === "cancelled")
        state = "fail";
    if (state === "evaluated") {
        if (task.exitcode === 0)
            state = "success";
        else
            state = "fail";
    }
    let color = colorCoding[state];

    let className = "";
    className += "bg-" + color[0] + "-" + ((index % 2) === 0 ? color[1] : color[2]);
    return className;
}

function SuiteTasks(props) {
    let tasks = props.tasks;

    let header = [
        <th className="w-1/12">ID</th>,
        <th className="w-1/12 text-left">State</th>,
        <th className="w-1/12 text-left">Assignee</th>,
        <th className="w-2/12 text-left">Last update</th>,
        <th className="text-left">Command</th>
    ]

    return <table className="w-full pl-4 table-fixed">
        <thead><tr>
            {header.map((e, i) => React.cloneElement(e, {"key": i}))}
        </tr></thead>
        <tbody>
            {
                tasks.map((task, i) => {
                    let colClass = "py-2 ";
                    let detail = <TaskDetail entityId={task.id}/>
                    return (
                        <ExpandableTableRow
                                key={i}
                                expandableContent={detail}
                                className={taskRowClass(task, i)}>
                            <td className={colClass + "text-center"}>{task.id}</td>
                            <td className={colClass + "text-left"}>{task.state}</td>
                            <td className={colClass + "text-left"}>{task.assignee}</td>
                            <td className={colClass + "text-left"}>{task.updatedAt}</td>
                            <td className={colClass + "text-left font-mono"}>{task.command}</td>
                        </ExpandableTableRow>)
                })
            }
        </tbody>
    </table>
}

class SuiteDetail extends EntityDetail {
    constructor(props) {
        super(SUITE_PROXY, props);
    }

    renderEntity(suite) {
        return <div className="w-full p-3 pl-16 border-black border-l-4">
            <h3 className="font-bold">
                Benchmark suite {suite.id}
            </h3>
            <p className="w-full border-b-2 border-gray">
                {suite.description}
            </p>
            <div className="w-full flex flex-wrap mt-2 border-b-2 border-gray">
                <div className="w-full md:w-1/2 p-2">
                    <h4 className="text-xl mb-2">Environment</h4>
                    <BenchamarkEnv env={suite.env}/>
                </div>
                <div className="w-full md:w-1/2 p-2">
                    <h4 className="text-xl mb-2">
                        Statistics
                    </h4>
                    <SuiteStatistics suite={suite}/>
                </div>
            </div>
            <div className="w-full p-2 border-b-2 border-gray my-2">
                <h4 className="text-xl">Tasks</h4>
                <SuiteTasks tasks={suite.tasks}/>
            </div>
        </div>
    }
}

function SuiteTable(props) {
    let header = [
        <th className="w-1/12">ID</th>,
        <th className="text-left w-2/12">Created</th>,
        <th className="text-left w-1/12">Author</th>,
        <th className="w-1/12">Completed</th>,
        <th className="text-left">Description</th>
    ]

    let tableBody;
    if (props.suites) {
        tableBody = props.suites.map((suite, i) => {
            let detail = <SuiteDetail entityId={suite.id}/>
            let colClass = "py-2 ";
            let rowClass = "p-2 ";
            if ((i % 2) === 0) {
                rowClass += "bg-gray-100 ";
            }
            else {
                rowClass += "bg-gray-200 ";
            }
            return (
                <ExpandableTableRow key={i} expandableContent={detail} className={rowClass}>
                    <td className={colClass + "text-center"}>{suite.id}</td>
                    <td className={colClass}>{suite.created}</td>
                    <td className={colClass}>{suite.author}</td>
                    <td className={colClass  + "text-center"}>{suite.completedTaskCount}/{suite.taskCount}</td>
                    <td className={colClass}>
                        <Link to={`suites/${suite.id}`}>
                            {suite.description}
                        </Link>
                    </td>
                </ExpandableTableRow>);
        })
    }
    else {
        tableBody = (
            <tr>
                <td colSpan={header.length}>
                    <Spinbox/>
                </td>
            </tr>);
    }
    return (
        <table className="w-full table-fixed break-words">
            <thead><tr>
                {header.map((e, i) => React.cloneElement(e, {"key": i}))}
            </tr></thead>
            <tbody>
                {tableBody}
            </tbody>
        </table>);
}

export class Overview extends React.Component {
    constructor(props) {
        super(props)
        this.state = {};
    }

    componentDidMount() {
        fetch("/api/suites").then(response => {
            if (!response.ok) {
                throw new Error(response.statusText);
            }
            if (response.status !== 200) {
                return response.text().then( text => {
                    throw new Error(`Response: ${response.status}: ${text}`);
                });
            }
            return response.json();
        }).then(responseJson => {
            this.setState({"suites": responseJson.suites})
        }).catch(e => {
            this.setState({"message": e.message});
        });
    }

    render() {
        let content;
        if (!(this.state.message || this.state.suites)) {
            content = <Spinbox/>;
        }
        else if (this.state.message) {
            content = <p>{this.state.message}</p>;
        }
        else {
            content = <SuiteTable suites={this.state.suites}/>;
        }

        return <>
            <h1>List of benchmarking suites</h1>
            {content}
        </>
    }
}

export function SuitePage() {
    let { entityId } = useParams();
    return <SuiteDetail entityId={entityId}/>
}
