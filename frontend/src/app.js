import React from 'react';
import {
  HashRouter as Router,
  Switch,
  Route,
  NavLink
} from "react-router-dom";
import { Overview, SuitePage } from './overview'
import { NewBenchmark } from './newbench'
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

function Container(props) {
  return <div className="container mx-auto px-2">{props.children}</div>
}

function Header(props) {
  return <div className="w-ful bg-blue-200 p-4">
      <img src="logo.svg" alt="" className="inline-block mr-6" style={{"width": "80px"}}/>
      <h1 className="inline-block">Surveyor &mdash; benchmarking made simple</h1>
  </div>
}

function Navbar(props) {
    return <div className="w-ful text-lg border-b-4 border-gray-200 mb-4">
        <NavLink to="/" exact={true}
            className="inline-block p-4 bg-white no-underline"
            activeClassName="bg-gray-200 font-bold">
            Overview
        </NavLink>
        <NavLink to="/new"
            className="inline-block p-4 bg-white no-underline"
            activeClassName="bg-gray-200 font-bold">
            Submit a new benchmarking task
        </NavLink>
    </div>
}

function Footer(props) {
    return <div className="w-full p-2 border-t-2 border-gray-800 text-gray-700 text-center text-xs" style={{"minHeight": "200px"}}>
        <p>Surveyor &mdash; benchmarking tool</p>
        <p>Developed at <a href="https://paradise.fi.muni.cz">Paradise FI MUNI</a></p>
        <p>Source code available on&nbsp;
            <a href="https://github.com/paradise-fi/surveyor">
                GitHub
            </a>
        </p>
    </div>
}

export function NoMatch() {
    return <p>404 not found</p>;
}

function App() {
    return (
        <Router basename="/" >
            <Container>
                <Header/>
                <Navbar/>
                <Switch>
                    <Route exact path="/">
                        <Overview/>
                    </Route>
                    <Route path="/suites/:entityId">
                        <SuitePage/>
                    </Route>
                    <Route path="/new">
                        <NewBenchmark/>
                    </Route>
                    <Route path="*">
                        <NoMatch />
                    </Route>
                </Switch>
                <Footer/>
            </Container>
            <ToastContainer />
        </Router>
    );
}

export default App;
