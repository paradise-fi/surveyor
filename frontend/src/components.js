import React from "react"

export function Spinbox() {
    return <div className="w-full text-center">
        <svg className="animate-spin -ml-1 m-8 h-5 w-5 text-black mx-auto inline-block"
             xmlns="http://www.w3.org/2000/svg"
             fill="none" viewBox="0 0 24 24"
             style={{"maxWidth": "100px", "maxHeight": "100px", "width": "100%", "height": "100%"}}>
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
    </div>
}

export function InlineSpinbox(props) {
    return <div className={`inline text-center ${props.className}`}>
        <svg className="animate-spin h-5 w-5 text-black mx-auto inline-block"
             xmlns="http://www.w3.org/2000/svg"
             fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
    </div>
}

export function timeLimitString(timelimit) {
    // Give a time limit in seconds, format it as string
    if (timelimit === undefined || timelimit === null || isNaN(timelimit))
        return "N/A"
    if (timelimit < 1) {
        return (timelimit * 1000).toFixed(3).toString() + "ms"
    }

    let hours = Math.floor(timelimit / 3600);
    let minutes = Math.floor(timelimit / 60) % 60;
    let seconds = timelimit % 60;

    let res = "";
    if (seconds !== 0)
        res = seconds.toString() + "s";
    if (minutes !== 0)
        res = minutes.toString() + "min " + res;
    if (hours !== 0)
        res = hours.toString() + "h " + res;
    return res;
}

export function memLimitString(bytes) {
    const thresh = 1024;
    if (Math.abs(bytes) < thresh) {
        return bytes + ' B';
    }

    const units = ['KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB'];
    let u = -1;
    const r = 10 ** 2;

    do {
        bytes /= thresh;
        ++u;
    } while (Math.round(Math.abs(bytes) * r) / r >= thresh && u < units.length - 1);


    return bytes.toFixed(2) + ' ' + units[u];
}

export function Button(props) {
    let {className, ...otherProps} = props;
    return <button className={"bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded disabled:bg-gray-500 disabled:cursor-not-allowed " + className}
            {...otherProps}>
        {props.children}
    </button>
}
