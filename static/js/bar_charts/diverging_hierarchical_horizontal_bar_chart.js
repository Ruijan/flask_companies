class DivergingHierarchicalHorizontalBarChart {
    constructor(container_name, data) {
        this.root = this.transformData(data)
        this.c_name = container_name
        this.margin = ({top: 30, right: 30, bottom: 30, left: 40})
        this.container = d3.select(container_name)
        this.width = this.container.node().getBoundingClientRect().width - this.margin.right - this.margin.left;
        this.height = this.width/3;
        this.barStep = this.width/this.getNbBars(this.root);
        this.barPadding = 3/this.barStep;
        this.container.style("height", (this.height + this.margin.bottom + this.margin.top)+"px");
        this.init()
        this.tooltip = d3.select(this.c_name)
            .append("div")
            .style("opacity", 0)
            .attr("class", "tooltip")
            .style("position", "absolute")
            .style("background-color", "white")
            .style("border", "none")
            .style("padding", "5px")
            .style("width", "auto")
            .style("color", "black")
        this.color = d3.scaleOrdinal([true, false], ["steelblue", "#aaa"])
        this.y = d3.scaleLinear().range([this.height - this.margin.bottom, this.margin.top])
        this.buildSVG();
    }

    init(){
        this.duration = 500
    }

    transformData(data) {
        return d3.hierarchy(data)
            .sort((a, b) => d3.ascending(a.data.name, b.data.name))
            .eachAfter(d => d.index = d.parent ? d.parent.index = d.parent.index + 1 || 0 : 0)
    }

    buildSVG(){
        this.updateYDomain(this.root, false);
        this.color = d3.scaleOrdinal([0, 1, 2], ["#b44682", "#82b446", "#aaa"])

        this.svg = this.container.append("svg")
            .attr("preserveAspectRatio", "xMinYMin meet")
            .attr("viewBox", "0 0 " + this.container.node().getBoundingClientRect().width + " " + this.height);
        this.svg.append("rect")
            .attr("class", "background")
            .attr("fill", "none")
            .attr("pointer-events", "all")
            .attr("height", this.height)
            .attr("width", this.width)
            .attr("cursor", "pointer")
            .on("click", d => this.up(d));
        this.yAxis = g => g
            .attr("class", "y-axis")
            .style("font", "14px sans-serif")
            .attr("transform", `translate(${this.margin.left+6},0)`)
            .call(d3.axisLeft(this.y).ticks(this.height / 80, "s").tickFormat(function(d){return d3.format(".2s")(d).replace(/G/, "B")}))
            .call(g => (g.selection ? g.selection() : g).select(".domain").remove())
        this.xAxis = g => g
            .attr("class", "x-axis")
            .attr("transform", `translate(${this.margin.left},0)`)
            .call(g => g.append("line")
                .attr("stroke", "currentColor")
                .attr("x1", this.margin.left)
                .attr("x2", this.width + this.margin.right)
                .attr("y1", this.center)
                .attr("y2", this.center))
        this.svg.append("g")
            .call(this.yAxis);
        this.svg.append("g")
            .call(this.xAxis);

        this.down(this.root);
    }

    getNbBars(data){
        let max = 1;
        data.each(d => d.children && (max = Math.max(max, d.children.length)));
        return max;
    }

    up(d) {
        if (!d.parent || !this.svg.selectAll(".exit").empty()) return;

        // Rebind the current node to the background.
        this.svg.select(".background").datum(d.parent);

        // Define two sequenced transitions.
        const transition1 = this.svg.transition().duration(this.duration);
        const transition2 = transition1.transition();
        let barStep = this.width/this.getNbBars(d.parent);
        // Mark any currently-displayed bars as exiting.
        const exit = this.svg.selectAll(".enter")
            .attr("class", "exit");
        let previous_center = this.center;
        // Update the y-scale domain.
        this.updateYDomain(d, true);
        // Update the y-axis.
        this.svg.selectAll(".y-axis").transition(transition1)
            .call(this.yAxis);
        this.svg.selectAll(".x-axis").transition(transition2)
            .attr("transform", `translate(0,,${-getYPos(0, this.y, this.center - previous_center)})`);

        // Transition exiting bars to the new y-scale.
        exit.selectAll("g").transition(transition1)
            .attr("transform", stagger(this.y, barStep));
        let previousBarStep = this.width/this.getNbBars(d);
        // Transition exiting bars to the parent’s position.
        exit.selectAll("g").transition(transition2)
            .attr("transform", stack(d.index, this.y, barStep, this.center - previous_center));

        // Transition exiting rects to the new scale and fade to parent color.
        exit.selectAll("rect").transition(transition1)
            .attr("height", d => getHeight(d.value, this.y))
            .attr("fill", d => d.value > 0 ? this.color(1) : this.color(0))
            .attr("transform", `scale(${barStep/previousBarStep}, 1)`);

        // Transition exiting text to fade out.
        // Remove exiting nodes.
        exit.transition(transition2)
            .attr("fill-opacity", 0)
            .remove();

        // Enter the new bars for the clicked-on data's parent.
        barStep = this.width/this.getNbBars(d.parent);
        const enter = this.createBar(d.parent, ".exit")
            .attr("fill-opacity", 0);

        // Transition entering bars to the new y-scale.
        enter.selectAll("g").transition(transition2)
            .attr("transform", (d, i) => `translate(${barStep * i}, ${getYPos(d.value, this.y, 0)})`)
        enter.selectAll("text")
            .attr("transform", (d, i) => `translate(0,${-getYPos(d.value, this.y, 0)})`);

        // Transition entering bars to fade in over the full duration.
        enter.transition(transition2)
            .attr("fill-opacity", 1);

        // Color the bars as appropriate.
        // Exiting nodes will obscure the parent bar, so hide it.
        // Transition entering rects to the new y-scale.
        // When the entering parent rect is done, make it visible!
        enter.selectAll("rect")
            .attr("fill", d => d.value > 0 ? this.color(1) : this.color(0))
            .attr("fill-opacity", p => p === d ? 0 : null)
            .transition(transition2)
            .attr("height", d => getHeight(d.value, this.y))
            .on("end", function(p) { d3.select(this).attr("fill-opacity", 1); });
    }

    down(d) {
        if (!d.children || d3.active(this.svg.node())) return;

        // Rebind the current node to the background.
        this.svg.select(".background").datum(d);

        // Define two sequenced transitions.
        const transition1 = this.svg.transition().duration(this.duration);
        const transition2 = transition1.transition();

        // Mark any currently-displayed bars as exiting.
        const exit = this.svg.selectAll(".enter")
            .attr("class", "exit");

        // Entering nodes immediately obscure the clicked-on bar, so hide it.
        exit.selectAll("rect")
            .attr("fill-opacity", p => p === d ? 0 : null);

        // Transition exiting bars to fade out.
        exit.transition(transition1)
            .attr("fill-opacity", 0)
            .remove();

        // Enter the new bars for the clicked-on data.
        // Per above, entering bars are immediately visible.
        let previous_center = this.center;
        if(d.parent !== null){
            this.updateYDomain(d, false);
        }
        let isCenterChanging = this.center !== previous_center
        if (!isCenterChanging && d.parent !== null){
            this.updateYDomain(d, true);
        }
        const enter = this.createBar(d, ".y-axis")
            .attr("fill-opacity", 0);
        let barStep = this.width/this.getNbBars(d);
        // Have the text fade-in, even though the bars are visible.
        enter.transition(transition1)
            .attr("fill-opacity", 1);

        // Transition entering bars to their new x-position.
        enter.selectAll("g")
            .attr("transform", stack(d.index, this.y, barStep, 0))
            .transition(transition1)
            .attr("transform", stagger(this.y, barStep));

        // Update the y-scale domain.
        if (!isCenterChanging){
            this.updateYDomain(d, false);
        }

        // Update the x-axis.
        this.svg.selectAll(".y-axis").transition(transition2)
            .call(this.yAxis);
        this.svg.selectAll(".x-axis").transition(transition1)
            .attr("transform", `translate(0, ${this.center - previous_center})`);

        // Transition entering bars to the new y-scale.
        enter.selectAll("g").transition(transition2)
            .attr("transform", (d, i) => `translate(${barStep * i},${getYPos(d.value, this.y, 0)})`)
        enter.selectAll("text")
            .attr("transform", (d, i) => `translate(0, ${-getYPos(d.value, this.y, 0)})`);

        // Color the bars as parents; they will fade to children if appropriate.
        enter.selectAll("rect")
            .attr("fill", d => d.value > 0 ? this.color(1) : this.color(0))
            .attr("fill-opacity", 1)
            .transition(transition2)
            .attr("fill", d => d.value > 0 ? this.color(1) : this.color(0))
            .attr("height", d => getHeight(d.value, this.y));
    }

    updateYDomain(d, up) {
        let minimum = 0;
        let maximum = 0;
        if(up){
            minimum = d3.min(d.parent.children, d => d.value);
            maximum = d3.max(d.parent.children, d => d.value);
        }
        else{
            minimum = d3.min(d.children, d => d.value);
            maximum = d3.max(d.children, d => d.value);
        }
        minimum = minimum > 0 ? 0 : minimum;

        this.y.domain([minimum * 1.1, maximum * 1.1]);
        this.center = this.y(0);

    }

// Creates a set of bars for the given data node, at the specified index.
    createBar(d, selector) {
        let chart = this;
        let barStep = this.width/this.getNbBars(d);
        let barPadding = 5/barStep;
        const g = this.svg.insert("g", selector)
            .attr("class", "enter")
            .attr("transform", `translate(${this.margin.left + barStep * barPadding},0)`)
            .attr("text-anchor", "middle")
            .style("font", "14px sans-serif").style('fill', 'cornsilk');

        const bar = g.selectAll("g")
            .data(d.children)
            .join("g")
            .attr("cursor", d => !d.children ? null : "pointer")
            .on("click", d => this.down(d));
        let max_labels = 10;
        let step_label = Math.ceil(this.getNbBars(d)/max_labels);
        bar.append("text")
            .attr("y", (d) => d.value > 0 ? this.center + 12 : this.center - 12 )
            .attr("x", barStep * (1 - barPadding) / 2)
            .attr("dy", ".35em")
            .attr('text-anchor', 'middle')
            .text((d, i) =>  i % step_label === 0 ? d.data.name : "").style('fill', 'cornsilk');

        // Three function that change the tooltip when user hover / move / leave a cell
        let mouseover = function(d) {
            chart.tooltip.style("opacity", 1)
        }
        let mousemove = function(d) {
            let tip = ""
            if(d.children != undefined){
                tip = "<tr><td style='text-align: left;'><span style='color: dodgerblue'>Quarters</span>: </td>" +
                    "<td style='text-align: right;'>" + getNumberOfChildren(d) + "</td></tr>" +
                    "<tr><td style='text-align: center; padding-left: 5px; padding-right: 5px; color: dodgerblue;' colspan='2'>Click on the bar to expand</td></tr>"
            }
            chart.tooltip
                .html("<table><tr><td style='text-align: left;'><span style='color: dodgerblue'>Name</span>: </td>" +
                    "<td style='text-align: right;'>" + d.data.name + "</td></tr>" +
                    "<tr><td style='text-align: left;'><span style='color: dodgerblue'>Amount</span>: </td>" +
                    "<td style='text-align: right;'>" + d3.format(".2s")(d.value).replace(/G/, "B") + "</td></tr>" +
                    tip +
                    "</table>")
                .style("top", (d3.event.pageY + 30)+"px")
                .style("left",(d3.event.pageX + 30)+"px")
        }
        let mouseleave = function(d) {
            chart.tooltip
                .style("opacity", 0)
        }
        bar.append("rect")
            .attr("y", this.center)
            .attr("height", d => getHeight(d.value, this.y))
            .attr("width", barStep * (1 - barPadding))
            .on('mouseenter', function (actual, i) {
                d3.select(this).attr('opacity', 0.5)
                bar.selectAll('#limit').remove()
                let pos_y = 0
                if(actual.value < 0){
                    pos_y = getYPos(actual.value, chart.y, chart.center) + getHeight(actual.value, chart.y);
                }
                else{
                    pos_y = getYPos(actual.value, chart.y, chart.center);
                }
                bar.append('line')
                    .attr('id', 'limit')
                    .attr('y1', (d) => pos_y + (d.value < 0 ? 0 : getHeight(d.value, chart.y)))
                    .attr('x1', 0)
                    .attr('y2', (d) => pos_y + (d.value < 0 ? 0 : getHeight(d.value, chart.y)))
                    .attr('x2', barStep)
                    .attr('stroke', 'red')
                bar.append('text')
                    .attr('class', 'divergence')
                    .attr('y', (a) => a.value < 0 ? chart.y(a.value) + 12 : chart.y(a.value) + getHeight(a.value, chart.y) - 12)
                    .attr('x', (a) => barStep * (1 - barPadding) / 2)
                    .attr('fill', 'white')
                    .attr('text-anchor', 'middle')
                    .text((a, idx) => {
                        const divergence = ((a.value - actual.value)/actual.value * 100).toFixed(1)
                        let text = ''
                        if (divergence > 0) text += '+'
                        text += `${divergence}%`
                        return idx !== i ? text : '';
                    })
            })
            .on('mouseover', mouseover)
            .on('mouseleave', function (actual, i) {
                d3.select(this).attr('opacity', 1)
                bar.selectAll('#limit').remove()
                bar.selectAll('.divergence').remove()
                mouseleave(actual);
            })
            .on('mousemove',mousemove);

        return g;
    }
}

function getYPos(y, range, offset){
    let value = Math.min(0, -(range(0) - range(y))) + offset
    return value;
}

function getHeight(y, range){
    let value = Math.abs(range(y) - range(0))
    return value;
}

function stagger(y, barStep) {
    let negative_value = 0;
    let positive_value = 0;
    return (d, i) => {
        let t;
        if(d.value < 0){
            t = `translate(${barStep * i},${y(negative_value) - y(0)})`;
            negative_value += d.value;

        }

        if(d.value > 0) {
            positive_value += d.value;
            t = `translate(${barStep * i},${y(positive_value) - y(0)})`;
        }
        return t;
    };
}

function stack(i, y, barStep, offset) {
    let negative_value = 0;
    let positive_value = 0;
    return (d) => {
        let t;
        if(d.value < 0){
            t = `translate(${barStep * i},${y(negative_value) - y(0) + offset})`;
            negative_value += d.value;
        }

        if(d.value > 0) {
            positive_value += d.value;
            t = `translate(${barStep * i},${y(positive_value) - y(0) + offset})`;
        }
        return t;
    };
}

function getNumberOfChildren(n) {
    if (n.children == undefined) return 1;
    var nb_children = 0;
    n.children.forEach(function(c){
        nb_children += getNumberOfChildren(c);
    });
    return nb_children;
}